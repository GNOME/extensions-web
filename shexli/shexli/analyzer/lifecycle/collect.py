# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from pathlib import Path

from tree_sitter import Node

from ...ast import (
    call_arguments,
    call_callee_parts,
    identifier_name,
    iter_nodes,
    member_expression_parts,
    node_text,
    variable_declarator_name,
    variable_declarator_value,
)
from ..evidence import node_evidence
from ..paths import PathMapper
from .base import (
    SELF_OWNER,
    SOURCE_ADD_NAMES,
    SOURCE_REMOVE_NAMES,
    CleanupCollector,
    ResourceTracker,
    field_name_from_node,
    is_release_value,
    is_signal_connect_call,
    owner_field_from_node,
    record_resource,
    resource_from_node,
)

LOCAL_UI_NAMESPACE_ROOTS = {
    "Adw",
    "Clutter",
    "Gtk",
    "PanelMenu",
    "PopupMenu",
    "QuickSettings",
    "St",
}


def collect_resources_from_methods(
    source: str,
    path: Path,
    methods: list[Node],
    mapper: PathMapper,
    destroyable_classes: set[str],
    module_vars: set[str],
) -> ResourceTracker:
    tracker = ResourceTracker.empty()
    for method in methods:
        body = method.child_by_field_name("body")
        if body is None:
            continue

        aliases: dict[str, str] = {}
        owner_aliases: dict[str, str] = {}
        cleared_sources: set[str] = set()
        menu_item_aliases: set[str] = set()
        local_ui_aliases: set[str] = set()
        local_menu_owned: set[str] = set()

        for node in iter_nodes(body):
            if node.type == "variable_declarator":
                name = variable_declarator_name(source, node)
                value = variable_declarator_value(node)

                if name and value is not None:
                    kind = resource_from_node(
                        source,
                        value,
                        aliases,
                        destroyable_classes,
                    )
                    if kind:
                        aliases[name] = kind
                    else:
                        field = field_name_from_node(
                            source,
                            value,
                            aliases,
                            module_vars,
                        )
                        if field:
                            aliases[name] = f"field:{field}"

                    owner = owner_field_from_node(
                        source,
                        value,
                        aliases,
                        owner_aliases,
                        module_vars,
                    )
                    if owner:
                        owner_aliases[name] = owner

                    if name and value is not None and value.type == "new_expression":
                        constructor = value.child_by_field_name("constructor")
                        constructor_parts = member_expression_parts(source, constructor)
                        constructor_name = ".".join(constructor_parts)
                        if constructor_name.startswith("PopupMenu.Popup"):
                            menu_item_aliases.add(name)
                        if (
                            constructor_parts
                            and constructor_parts[0] in LOCAL_UI_NAMESPACE_ROOTS
                        ):
                            local_ui_aliases.add(name)
            elif node.type == "assignment_expression":
                left = node.child_by_field_name("left")
                right = node.child_by_field_name("right")

                if left is None or right is None:
                    continue

                left_field = field_name_from_node(
                    source,
                    left,
                    aliases,
                    module_vars,
                )
                if left_field:
                    kind = resource_from_node(
                        source,
                        right,
                        aliases,
                        destroyable_classes,
                    )
                    evidence = node_evidence(path, source, node, mapper)
                    if kind == "signal":
                        record_resource(tracker.signals, left_field, evidence)
                    elif kind == "source":
                        if (
                            left_field in tracker.sources
                            and left_field not in cleared_sources
                        ):
                            record_resource(
                                tracker.recreated_sources,
                                left_field,
                                evidence,
                            )
                        record_resource(tracker.sources, left_field, evidence)
                        cleared_sources.discard(left_field)
                    elif kind == "object":
                        record_resource(tracker.objects, left_field, evidence)
                    elif kind == "resource_ref":
                        record_resource(tracker.resource_refs, left_field, evidence)
                    elif kind == "container":
                        record_resource(tracker.containers, left_field, evidence)
                elif left.type == "identifier":
                    name = identifier_name(source, left)
                    if name:
                        kind = resource_from_node(
                            source,
                            right,
                            aliases,
                            destroyable_classes,
                        )
                        if kind:
                            aliases[name] = kind

                        owner = owner_field_from_node(
                            source,
                            right,
                            aliases,
                            owner_aliases,
                            module_vars,
                        )
                        if owner:
                            owner_aliases[name] = owner
                        if right.type == "new_expression":
                            constructor = right.child_by_field_name("constructor")
                            constructor_parts = member_expression_parts(
                                source,
                                constructor,
                            )
                            if (
                                constructor_parts
                                and constructor_parts[0] in LOCAL_UI_NAMESPACE_ROOTS
                            ):
                                local_ui_aliases.add(name)
            elif node.type == "call_expression":
                function_node = node.child_by_field_name("function")
                if function_node is None:
                    continue

                call_name = ".".join(call_callee_parts(source, node))
                if (
                    is_signal_connect_call(source, node)
                    and node.parent is not None
                    and node.parent.type == "expression_statement"
                ):
                    receiver = function_node.child_by_field_name("object")
                    signal_args = call_arguments(node)
                    signal_event = None
                    if signal_args and signal_args[0].type == "string":
                        signal_event = node_text(source, signal_args[0]).strip("\"'")

                    if (
                        signal_event == "activate"
                        and receiver is not None
                        and receiver.type == "identifier"
                    ):
                        receiver_name = identifier_name(source, receiver)
                        if receiver_name in menu_item_aliases:
                            continue

                    if receiver is not None and receiver.type == "identifier":
                        receiver_name = identifier_name(source, receiver)
                        if receiver_name and (
                            aliases.get(receiver_name) == "object"
                            or receiver_name in local_ui_aliases
                        ):
                            continue

                    receiver_field = None
                    if receiver is not None:
                        receiver_field = field_name_from_node(
                            source,
                            receiver,
                            aliases,
                            module_vars,
                        )
                        if receiver_field is None and receiver.type == "identifier":
                            receiver_name = identifier_name(source, receiver)
                            if aliases.get(receiver_name or "") == "object":
                                receiver_field = receiver_name
                    evidence = node_evidence(path, source, node, mapper)
                    signal_name = (
                        f"anonymous-signal:{signal_event}:{node.start_point.row + 1}"
                        if signal_event
                        else f"anonymous-signal:{node.start_point.row + 1}"
                    )
                    if receiver_field:
                        signal_name = (
                            "anonymous-signal:"
                            f"{receiver_field}:"
                            f"{signal_event}:{node.start_point.row + 1}"
                            if signal_event
                            else f"{receiver_field}:{node.start_point.row + 1}"
                        )
                    record_resource(tracker.signals, signal_name, evidence)

                if (
                    call_name in SOURCE_ADD_NAMES
                    and node.parent is not None
                    and node.parent.type == "expression_statement"
                ):
                    evidence = node_evidence(path, source, node, mapper)
                    record_resource(
                        tracker.sources,
                        f"anonymous-source:{node.start_point.row + 1}",
                        evidence,
                    )

                callee_parts = member_expression_parts(source, function_node)
                if (
                    len(callee_parts) == 3
                    and (callee_parts[0] == "this" or callee_parts[0] in module_vars)
                    and callee_parts[2] in {"push", "add"}
                ):
                    container = (
                        callee_parts[1]
                        if callee_parts[0] == "this"
                        else callee_parts[0]
                    )

                    for arg in call_arguments(node):
                        kind = resource_from_node(
                            source,
                            arg,
                            aliases,
                            destroyable_classes,
                        )
                        evidence = node_evidence(path, source, arg, mapper)
                        if kind == "signal":
                            record_resource(tracker.signal_groups, container, evidence)
                        elif kind == "source":
                            record_resource(tracker.source_groups, container, evidence)
                        elif kind == "object":
                            record_resource(tracker.object_groups, container, evidence)

                if callee_parts and callee_parts[-1] in {
                    "add_child",
                    "set_child",
                    "add_actor",
                    "addMenuItem",
                }:
                    is_menu_item_add = callee_parts[-1] == "addMenuItem"
                    parent_node = function_node.child_by_field_name("object")
                    local_parent_name = None
                    if parent_node is not None and parent_node.type == "identifier":
                        parent_name = identifier_name(source, parent_node)
                        if parent_name and aliases.get(parent_name) == "object":
                            local_parent_name = parent_name
                    parent = owner_field_from_node(
                        source,
                        parent_node if parent_node is not None else function_node,
                        aliases,
                        owner_aliases,
                        module_vars,
                    )
                    if (
                        parent is None
                        and parent_node is not None
                        and parent_node.type == "this"
                    ):
                        parent = SELF_OWNER
                    if parent is None and local_parent_name is None:
                        continue

                    for arg in call_arguments(node):
                        child = field_name_from_node(
                            source,
                            arg,
                            aliases,
                            module_vars,
                        )
                        if child and child != parent:
                            if parent is not None:
                                tracker.parent_owned.setdefault(child, parent)
                            if is_menu_item_add:
                                tracker.menu_owned.add(child)
                            if local_parent_name:
                                tracker.local_parent_owned.setdefault(
                                    child,
                                    local_parent_name,
                                )

                        if arg.type == "identifier":
                            name = identifier_name(source, arg)
                            if name and aliases.get(name) == "object":
                                if parent is not None:
                                    tracker.local_parent_owned.setdefault(name, parent)
                                if local_parent_name:
                                    tracker.local_parent_owned.setdefault(
                                        name,
                                        local_parent_name,
                                    )
                                if is_menu_item_add:
                                    tracker.menu_owned.add(name)
                                    local_menu_owned.add(name)

                if call_name in SOURCE_REMOVE_NAMES:
                    for arg in call_arguments(node):
                        field = field_name_from_node(
                            source,
                            arg,
                            aliases,
                            module_vars,
                        )
                        if field:
                            cleared_sources.add(field)

        changed = True
        while changed:
            changed = False
            for child, parent in tracker.parent_owned.items():
                if parent in tracker.menu_owned and child not in tracker.menu_owned:
                    tracker.menu_owned.add(child)
                    changed = True
            for child, parent in tracker.local_parent_owned.items():
                if parent in tracker.menu_owned and child not in tracker.menu_owned:
                    tracker.menu_owned.add(child)
                    local_menu_owned.add(child)
                    changed = True

    return tracker


def collect_cleanup_from_methods(
    source: str,
    methods: list[Node],
    module_vars: set[str],
) -> ResourceTracker:
    tracker = ResourceTracker.empty()
    for method in methods:
        body = method.child_by_field_name("body")
        if body is None:
            continue

        aliases: dict[str, str] = {}
        collector = CleanupCollector(source, aliases, module_vars, tracker)

        for node in iter_nodes(body):
            if node.type == "variable_declarator":
                name = variable_declarator_name(source, node)
                value = variable_declarator_value(node)

                if name and value is not None:
                    field = field_name_from_node(
                        source,
                        value,
                        module_vars=module_vars,
                    )
                    if field:
                        aliases[name] = f"field:{field}"
            elif node.type == "call_expression":
                collector.mark_call(node)

                function_node = node.child_by_field_name("function")
                if function_node is None:
                    continue

                function_parts = member_expression_parts(source, function_node)
                if (
                    len(function_parts) == 3
                    and function_parts[0] == "this"
                    and function_parts[2] == "forEach"
                ):
                    container = function_parts[1]
                    arguments = call_arguments(node)
                    if not arguments:
                        continue

                    callback = arguments[0]
                    if callback.type not in {"arrow_function", "function"}:
                        continue

                    callback_body = callback.child_by_field_name("body")
                    if callback_body is None:
                        continue

                    param = None
                    params = callback.child_by_field_name("parameters")
                    if params is not None and params.named_children:
                        param = identifier_name(source, params.named_children[0])
                    elif callback.named_children:
                        first_named = callback.named_children[0]
                        if first_named is not callback_body:
                            param = identifier_name(source, first_named)

                    if not param:
                        continue

                    _collect_loop_cleanup(
                        source,
                        callback_body,
                        container,
                        tracker,
                        param,
                    )
            elif node.type == "assignment_expression":
                left = node.child_by_field_name("left")
                right = node.child_by_field_name("right")

                if left is None or right is None:
                    continue

                field = field_name_from_node(
                    source,
                    left,
                    aliases,
                    module_vars,
                )
                if not field:
                    continue

                if is_release_value(source, right):
                    record_resource(tracker.released_refs, field)
            elif node.type == "for_in_statement":
                named = list(node.named_children)
                if len(named) < 3:
                    continue

                loop_var = identifier_name(source, named[0])
                iterable = named[1]
                body_node = named[2]
                container = field_name_from_node(
                    source,
                    iterable,
                    module_vars=module_vars,
                )

                if not loop_var or not container:
                    continue

                _collect_loop_cleanup(
                    source,
                    body_node,
                    container,
                    tracker,
                    loop_var,
                    match_first_argument=True,
                )

    return tracker


def _collect_loop_cleanup(
    source: str,
    body_node: Node,
    container: str,
    tracker: ResourceTracker,
    item_name: str,
    *,
    match_first_argument: bool = False,
) -> None:
    for sub in iter_nodes(body_node):
        if sub.type != "call_expression":
            continue

        call_name = ".".join(call_callee_parts(source, sub))
        args = call_arguments(sub)
        if not match_first_argument or (
            args
            and args[0].type == "identifier"
            and identifier_name(source, args[0]) == item_name
        ):
            if call_name.endswith(".disconnect") or call_name == "disconnect":
                record_resource(tracker.signal_groups, container)
                continue
            if call_name in SOURCE_REMOVE_NAMES:
                record_resource(tracker.source_groups, container)
                continue

        fn = sub.child_by_field_name("function")
        if fn is None:
            continue

        parts = member_expression_parts(source, fn)
        if len(parts) != 2:
            continue

        if parts[0] == item_name and parts[1] == "destroy":
            record_resource(tracker.object_groups, container)
