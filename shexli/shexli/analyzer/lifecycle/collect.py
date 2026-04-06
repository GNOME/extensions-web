# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass, field
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
from .cross_file import collect_cross_file_cleanup, collect_cross_file_resources
from .types import CrossFileIndex

LOCAL_UI_NAMESPACE_ROOTS = {
    "Adw",
    "Clutter",
    "Gtk",
    "PanelMenu",
    "PopupMenu",
    "QuickSettings",
    "St",
}


@dataclass
class ResourceCollector:
    """Stateful collector that scans method bodies and accumulates resource tracking."""

    source: str
    path: Path
    mapper: PathMapper
    destroyable_classes: set[str]
    module_vars: set[str]
    known_signal_manager_fields: set[str]

    tracker: ResourceTracker = field(default_factory=ResourceTracker)

    # Per-method state — reset by _begin_method() on each new method body.
    aliases: dict[str, str] = field(default_factory=dict)
    owner_aliases: dict[str, str] = field(default_factory=dict)
    cleared_sources: set[str] = field(default_factory=set)
    signal_manager_fields: set[str] = field(default_factory=set)
    menu_item_aliases: set[str] = field(default_factory=set)
    local_ui_aliases: set[str] = field(default_factory=set)
    local_menu_owned: set[str] = field(default_factory=set)
    local_parent_owned_names: set[str] = field(default_factory=set)
    method_signal_names: set[str] = field(default_factory=set)

    def _begin_method(self) -> None:
        self.aliases = {}
        self.owner_aliases = {}
        self.cleared_sources = set()
        self.signal_manager_fields = set(self.known_signal_manager_fields)
        self.menu_item_aliases = set()
        self.local_ui_aliases = set()
        self.local_menu_owned = set()
        self.local_parent_owned_names = set()
        self.method_signal_names = set()

    def _handle_variable_declarator(self, node: Node) -> None:
        name = variable_declarator_name(self.source, node)
        value = variable_declarator_value(node)

        if not name or value is None:
            return

        kind = resource_from_node(
            self.source,
            value,
            self.aliases,
            self.destroyable_classes,
        )
        if kind:
            self.aliases[name] = kind
            if kind == "signal_manager":
                self.signal_manager_fields.add(name)
        else:
            f = field_name_from_node(
                self.source,
                value,
                self.aliases,
                self.module_vars,
            )
            if f:
                self.aliases[name] = f"field:{f}"

        owner = owner_field_from_node(
            self.source,
            value,
            self.aliases,
            self.owner_aliases,
            self.module_vars,
        )
        if owner:
            self.owner_aliases[name] = owner

        if value.type == "new_expression":
            constructor = value.child_by_field_name("constructor")
            constructor_parts = member_expression_parts(self.source, constructor)
            constructor_name = ".".join(constructor_parts)
            if constructor_name.startswith("PopupMenu.Popup"):
                self.menu_item_aliases.add(name)
            if constructor_parts and constructor_parts[0] in LOCAL_UI_NAMESPACE_ROOTS:
                self.local_ui_aliases.add(name)

    def _handle_assignment(self, node: Node) -> None:
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")

        if left is None or right is None:
            return

        left_field = field_name_from_node(
            self.source,
            left,
            self.aliases,
            self.module_vars,
        )
        if left_field:
            kind = resource_from_node(
                self.source,
                right,
                self.aliases,
                self.destroyable_classes,
            )
            evidence = node_evidence(self.path, self.source, node, self.mapper)
            if kind == "signal_manager":
                self.signal_manager_fields.add(left_field)
            if kind == "signal":
                record_resource(self.tracker.signals, left_field, evidence)
            elif kind == "source":
                if (
                    left_field in self.tracker.sources
                    and left_field not in self.cleared_sources
                ):
                    record_resource(
                        self.tracker.recreated_sources,
                        left_field,
                        evidence,
                    )
                record_resource(self.tracker.sources, left_field, evidence)
                self.cleared_sources.discard(left_field)
            elif kind == "object":
                record_resource(self.tracker.objects, left_field, evidence)
            elif kind == "resource_ref":
                record_resource(self.tracker.resource_refs, left_field, evidence)
            elif kind == "container":
                record_resource(self.tracker.containers, left_field, evidence)
        elif left.type == "identifier":
            name = identifier_name(self.source, left)
            if name:
                kind = resource_from_node(
                    self.source,
                    right,
                    self.aliases,
                    self.destroyable_classes,
                )
                if kind:
                    self.aliases[name] = kind

                owner = owner_field_from_node(
                    self.source,
                    right,
                    self.aliases,
                    self.owner_aliases,
                    self.module_vars,
                )
                if owner:
                    self.owner_aliases[name] = owner
                if right.type == "new_expression":
                    constructor = right.child_by_field_name("constructor")
                    constructor_parts = member_expression_parts(
                        self.source,
                        constructor,
                    )
                    if (
                        constructor_parts
                        and constructor_parts[0] in LOCAL_UI_NAMESPACE_ROOTS
                    ):
                        self.local_ui_aliases.add(name)

    def _handle_signal_connect(
        self,
        node: Node,
        function_node: Node,
        call_name: str,
    ) -> None:
        receiver = function_node.child_by_field_name("object")
        signal_args = call_arguments(node)
        signal_event = None
        if signal_args and signal_args[0].type == "string":
            signal_event = node_text(self.source, signal_args[0]).strip("\"'")

        if (
            signal_event == "activate"
            and receiver is not None
            and receiver.type == "identifier"
        ):
            receiver_name = identifier_name(self.source, receiver)
            if receiver_name in self.menu_item_aliases:
                return

        if receiver is not None and receiver.type == "identifier":
            receiver_name = identifier_name(self.source, receiver)
            if receiver_name and self.aliases.get(receiver_name) == "signal_manager":
                evidence = node_evidence(self.path, self.source, node, self.mapper)
                record_resource(
                    self.tracker.signal_groups,
                    receiver_name,
                    evidence,
                )
                return
            if receiver_name and (
                self.aliases.get(receiver_name) == "object"
                or receiver_name in self.local_ui_aliases
            ):
                return

        receiver_field = None
        if receiver is not None:
            receiver_field = field_name_from_node(
                self.source,
                receiver,
                self.aliases,
                self.module_vars,
            )
            if receiver_field is None and receiver.type == "identifier":
                receiver_name = identifier_name(self.source, receiver)
                if self.aliases.get(receiver_name or "") == "object":
                    receiver_field = receiver_name
        evidence = node_evidence(self.path, self.source, node, self.mapper)
        signal_name = (
            f"anonymous-signal:{signal_event}:{node.start_point.row + 1}"
            if signal_event
            else f"anonymous-signal:{node.start_point.row + 1}"
        )
        if receiver_field:
            if receiver_field in self.signal_manager_fields:
                record_resource(
                    self.tracker.signal_groups,
                    receiver_field,
                    evidence,
                )
                return
            receiver_name = (
                identifier_name(self.source, receiver)
                if receiver is not None and receiver.type == "identifier"
                else None
            )
            if receiver_name and self.aliases.get(receiver_name) == "signal_manager":
                record_resource(
                    self.tracker.signal_groups,
                    receiver_field,
                    evidence,
                )
                return
            signal_name = (
                "anonymous-signal:"
                f"{receiver_field}:"
                f"{signal_event}:{node.start_point.row + 1}"
                if signal_event
                else f"{receiver_field}:{node.start_point.row + 1}"
            )
        elif receiver is not None and receiver.type == "identifier":
            receiver_name = identifier_name(self.source, receiver)
            if receiver_name:
                signal_name = (
                    "anonymous-signal:"
                    f"{receiver_name}:"
                    f"{signal_event}:{node.start_point.row + 1}"
                    if signal_event
                    else f"{receiver_name}:{node.start_point.row + 1}"
                )
        record_resource(self.tracker.signals, signal_name, evidence)
        self.method_signal_names.add(signal_name)

    def _handle_child_add(
        self, node: Node, function_node: Node, callee_parts: list[str]
    ) -> None:
        is_menu_item_add = callee_parts[-1] == "addMenuItem"
        uses_add_child_wrapper = callee_parts[-1] == "addChildToParent"
        parent_node = function_node.child_by_field_name("object")
        if uses_add_child_wrapper:
            arguments = call_arguments(node)
            if not arguments:
                return
            parent_node = arguments[0]
        local_parent_name = None
        if parent_node is not None and parent_node.type == "identifier":
            parent_name = identifier_name(self.source, parent_node)
            if parent_name and self.aliases.get(parent_name) == "object":
                local_parent_name = parent_name
        parent = owner_field_from_node(
            self.source,
            parent_node if parent_node is not None else function_node,
            self.aliases,
            self.owner_aliases,
            self.module_vars,
        )
        if parent is None and parent_node is not None and parent_node.type == "this":
            parent = SELF_OWNER
        if parent is None and local_parent_name is None:
            return

        child_args = (
            call_arguments(node)[1:] if uses_add_child_wrapper else call_arguments(node)
        )
        for arg in child_args:
            child = field_name_from_node(
                self.source,
                arg,
                self.aliases,
                self.module_vars,
            )
            if child and child != parent:
                if parent is not None:
                    self.tracker.parent_owned.setdefault(child, parent)
                if is_menu_item_add:
                    self.tracker.menu_owned.add(child)
                if local_parent_name:
                    self.tracker.local_parent_owned.setdefault(
                        child,
                        local_parent_name,
                    )

            if arg.type == "identifier":
                name = identifier_name(self.source, arg)
                if name and not self.aliases.get(name, "").startswith("field:"):
                    if parent is not None:
                        self.tracker.local_parent_owned.setdefault(name, parent)
                        self.local_parent_owned_names.add(name)
                    if local_parent_name:
                        self.tracker.local_parent_owned.setdefault(
                            name,
                            local_parent_name,
                        )
                        self.local_parent_owned_names.add(name)
                    if is_menu_item_add:
                        self.tracker.menu_owned.add(name)
                        self.local_menu_owned.add(name)

    def _handle_call(self, node: Node) -> None:
        function_node = node.child_by_field_name("function")
        if function_node is None:
            return

        call_name = ".".join(call_callee_parts(self.source, node))
        if (
            call_name == "Context.monitors.connect"
            and node.parent is not None
            and node.parent.type == "expression_statement"
        ):
            arguments = call_arguments(node)
            if arguments:
                owner = (
                    SELF_OWNER
                    if arguments[0].type == "this"
                    else field_name_from_node(
                        self.source,
                        arguments[0],
                        self.aliases,
                        self.module_vars,
                    )
                )
                if owner:
                    evidence = node_evidence(self.path, self.source, node, self.mapper)
                    record_resource(self.tracker.signal_groups, owner, evidence)
                    return
        if (
            is_signal_connect_call(self.source, node)
            and node.parent is not None
            and node.parent.type == "expression_statement"
        ):
            self._handle_signal_connect(node, function_node, call_name)

        if (
            call_name in SOURCE_ADD_NAMES
            and node.parent is not None
            and node.parent.type == "expression_statement"
        ):
            evidence = node_evidence(self.path, self.source, node, self.mapper)
            record_resource(
                self.tracker.sources,
                f"anonymous-source:{node.start_point.row + 1}",
                evidence,
            )

        callee_parts = member_expression_parts(self.source, function_node)
        if (
            len(callee_parts) == 3
            and (callee_parts[0] == "this" or callee_parts[0] in self.module_vars)
            and callee_parts[2] in {"push", "add"}
        ):
            container = (
                callee_parts[1] if callee_parts[0] == "this" else callee_parts[0]
            )

            for arg in call_arguments(node):
                kind = resource_from_node(
                    self.source,
                    arg,
                    self.aliases,
                    self.destroyable_classes,
                )
                evidence = node_evidence(self.path, self.source, arg, self.mapper)
                if kind == "signal":
                    record_resource(self.tracker.signal_groups, container, evidence)
                elif kind == "source":
                    record_resource(self.tracker.source_groups, container, evidence)
                elif kind == "object":
                    record_resource(self.tracker.object_groups, container, evidence)

        if callee_parts and callee_parts[-1] in {
            "add_child",
            "set_child",
            "add_actor",
            "addMenuItem",
            "addChildToParent",
        }:
            self._handle_child_add(node, function_node, callee_parts)

        if call_name in SOURCE_REMOVE_NAMES:
            for arg in call_arguments(node):
                f = field_name_from_node(
                    self.source,
                    arg,
                    self.aliases,
                    self.module_vars,
                )
                if f:
                    self.cleared_sources.add(f)

    def _finalize_method(self) -> None:
        changed = True
        while changed:
            changed = False
            for child, parent in self.tracker.parent_owned.items():
                if (
                    parent in self.tracker.menu_owned
                    and child not in self.tracker.menu_owned
                ):
                    self.tracker.menu_owned.add(child)
                    changed = True
            for child, parent in self.tracker.local_parent_owned.items():
                if (
                    parent in self.tracker.menu_owned
                    and child not in self.tracker.menu_owned
                ):
                    self.tracker.menu_owned.add(child)
                    self.local_menu_owned.add(child)
                    changed = True

        owned_local_names = self.local_parent_owned_names | self.local_menu_owned
        for signal_name in self.method_signal_names:
            if any(
                signal_name.startswith(f"anonymous-signal:{child}:")
                or signal_name.startswith(f"{child}:")
                for child in owned_local_names
            ):
                self.tracker.signals.pop(signal_name, None)

    def collect(
        self,
        methods: list[Node],
        cross_file_index: CrossFileIndex | None = None,
    ) -> ResourceTracker:
        for method in methods:
            body = method.child_by_field_name("body")
            if body is None:
                continue

            self._begin_method()

            for node in iter_nodes(body):
                if node.type == "variable_declarator":
                    self._handle_variable_declarator(node)
                elif node.type == "assignment_expression":
                    self._handle_assignment(node)
                elif node.type == "call_expression":
                    self._handle_call(node)

            self._finalize_method()

        if cross_file_index:
            collect_cross_file_resources(
                self.tracker,
                cross_file_index,
                self.source,
                methods,
                self.mapper,
                self.destroyable_classes,
            )

        return self.tracker


def collect_resources_from_methods(
    source: str,
    path: Path,
    methods: list[Node],
    mapper: PathMapper,
    destroyable_classes: set[str],
    module_vars: set[str],
    known_signal_manager_fields: set[str] | None = None,
    cross_file_index: CrossFileIndex | None = None,
) -> ResourceTracker:
    return ResourceCollector(
        source=source,
        path=path,
        mapper=mapper,
        destroyable_classes=destroyable_classes,
        module_vars=module_vars,
        known_signal_manager_fields=known_signal_manager_fields or set(),
    ).collect(methods, cross_file_index)


def collect_signal_manager_fields(
    source: str,
    methods: list[Node],
    destroyable_classes: set[str],
    module_vars: set[str],
) -> set[str]:
    fields: set[str] = set()

    for method in methods:
        body = method.child_by_field_name("body")
        if body is None:
            continue

        aliases: dict[str, str] = {}
        for node in iter_nodes(body):
            if node.type == "variable_declarator":
                name = variable_declarator_name(source, node)
                value = variable_declarator_value(node)
                if not name or value is None:
                    continue

                kind = resource_from_node(
                    source,
                    value,
                    aliases,
                    destroyable_classes,
                )
                if kind:
                    aliases[name] = kind
                    if kind == "signal_manager":
                        fields.add(name)
                else:
                    field = field_name_from_node(
                        source,
                        value,
                        aliases,
                        module_vars,
                    )
                    if field:
                        aliases[name] = f"field:{field}"
            elif node.type == "assignment_expression":
                left = node.child_by_field_name("left")
                right = node.child_by_field_name("right")
                if left is None or right is None:
                    continue

                kind = resource_from_node(
                    source,
                    right,
                    aliases,
                    destroyable_classes,
                )
                if kind != "signal_manager":
                    continue

                left_field = field_name_from_node(
                    source,
                    left,
                    aliases,
                    module_vars,
                )
                if left_field:
                    fields.add(left_field)
                elif left.type == "identifier":
                    name = identifier_name(source, left)
                    if name:
                        fields.add(name)

    return fields


def collect_cleanup_from_methods(
    source: str,
    methods: list[Node],
    module_vars: set[str],
    signal_group_fields: set[str] | None = None,
    cross_file_index: CrossFileIndex | None = None,
) -> ResourceTracker:
    tracker = ResourceTracker()
    signal_group_fields = signal_group_fields or set()
    for method in methods:
        body = method.child_by_field_name("body")
        if body is None:
            continue

        aliases: dict[str, str] = {}
        collector = CleanupCollector(
            source,
            aliases,
            module_vars,
            signal_group_fields,
            tracker,
        )

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

    if cross_file_index:
        collect_cross_file_cleanup(tracker, cross_file_index, source, methods)

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
