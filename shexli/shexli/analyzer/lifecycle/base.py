# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass

from tree_sitter import Node

from ...api_data import API
from ...ast import (
    bound_this_callback_methods,
    call_arguments,
    call_callee_parts,
    callback_identifier_arguments,
    child_by_type,
    direct_identifier_calls,
    direct_this_method_calls,
    identifier_name,
    iter_nodes,
    member_expression_parts,
    member_expression_property,
    node_text,
)
from ...models import Evidence

TOP_LEVEL_FORBIDDEN_NEW_PREFIXES = API.lifecycle.forbidden_new_prefixes
DESTROYABLE_NAMESPACE_ROOTS = API.lifecycle.destroyable_namespace_roots
DESTROYABLE_SUPERCLASS_NAMES = API.lifecycle.destroyable_superclass_names
RESOURCE_REF_CALL_NAMES = API.lifecycle.resource_ref_call_names
RESOURCE_REF_NEW_NAMES = API.lifecycle.resource_ref_new_names
SOURCE_ADD_NAMES = API.lifecycle.source_add_names
SOURCE_REMOVE_NAMES = API.lifecycle.source_remove_names
SIGNAL_MANAGER_NEW_NAMES = API.lifecycle.signal_manager_new_names

JS_BUILTIN_CONTAINERS = {
    "Array",
    "Date",
    "Map",
    "Object",
    "Promise",
    "RegExp",
    "Set",
    "URL",
    "WeakMap",
    "WeakSet",
}
NON_IMMEDIATE_EXECUTION_NODES = {
    "arrow_function",
    "class",
    "class_declaration",
    "function",
    "function_declaration",
    "function_expression",
    "generator_function",
    "generator_function_declaration",
    "method_definition",
}
SELF_OWNER = "__self_owner__"


@dataclass(slots=True)
class ResourceTracker:
    signals: dict[str, Evidence | None]
    sources: dict[str, Evidence | None]
    recreated_sources: dict[str, Evidence | None]
    objects: dict[str, Evidence | None]
    resource_refs: dict[str, Evidence | None]
    containers: dict[str, Evidence | None]
    parent_owned: dict[str, str]
    local_parent_owned: dict[str, str]
    menu_owned: set[str]
    signal_groups: dict[str, Evidence | None]
    source_groups: dict[str, Evidence | None]
    object_groups: dict[str, Evidence | None]
    released_refs: dict[str, Evidence | None]
    touched_refs: dict[str, Evidence | None]

    @classmethod
    def empty(cls) -> ResourceTracker:
        return cls({}, {}, {}, {}, {}, {}, {}, {}, set(), {}, {}, {}, {}, {})


def record_resource(
    resources: dict[str, Evidence | None],
    name: str,
    evidence: Evidence | None = None,
) -> None:
    if name in resources:
        return

    resources[name] = evidence


@dataclass(slots=True)
class CleanupCollector:
    source: str
    aliases: dict[str, str]
    module_vars: set[str]
    signal_group_fields: set[str]
    tracker: ResourceTracker

    def mark_call(self, node: Node) -> None:
        call_name = ".".join(call_callee_parts(self.source, node))
        function_node = node.child_by_field_name("function")
        if function_node is None:
            return

        function_parts = member_expression_parts(self.source, function_node)
        if (
            len(function_parts) == 3
            and function_parts[0] == "this"
            and function_parts[2] == "destroy"
        ):
            record_resource(self.tracker.objects, function_parts[1])
            if function_parts[1] in self.signal_group_fields:
                record_resource(self.tracker.signal_groups, function_parts[1])
            return

        if (
            len(function_parts) == 2
            and function_parts[0] in self.module_vars
            and function_parts[1] == "destroy"
        ):
            record_resource(self.tracker.objects, function_parts[0])
            if function_parts[0] in self.signal_group_fields:
                record_resource(self.tracker.signal_groups, function_parts[0])
            return

        if len(function_parts) >= 3 and function_parts[0] == "this":
            record_resource(self.tracker.touched_refs, function_parts[1])
        elif len(function_parts) >= 2 and function_parts[0] in self.module_vars:
            record_resource(self.tracker.touched_refs, function_parts[0])

        args = call_arguments(node)
        if call_name == "Context.monitors.disconnect":
            for arg in args:
                if arg.type == "this":
                    record_resource(self.tracker.signal_groups, SELF_OWNER)
                    return
        if call_name.endswith(".disconnect") or call_name == "disconnect":
            receiver = function_node.child_by_field_name("object")
            if not args and receiver is not None:
                field = field_name_from_node(
                    self.source,
                    receiver,
                    self.aliases,
                    self.module_vars,
                )
                if field:
                    record_resource(self.tracker.signal_groups, field)
                    return
            for arg in args:
                field = field_name_from_node(
                    self.source,
                    arg,
                    self.aliases,
                    self.module_vars,
                )
                if field:
                    record_resource(self.tracker.signals, field)
                elif arg.type == "identifier":
                    name = identifier_name(self.source, arg)
                    if name and self.aliases.get(name, "").startswith("group:signal:"):
                        record_resource(
                            self.tracker.signal_groups,
                            self.aliases[name].split(":", 2)[2],
                        )
        elif call_name.endswith(".disconnectAll"):
            receiver = function_node.child_by_field_name("object")
            if not args and receiver is not None:
                field = field_name_from_node(
                    self.source,
                    receiver,
                    self.aliases,
                    self.module_vars,
                )
                if field:
                    record_resource(self.tracker.signal_groups, field)
        elif call_name.endswith(".destroy"):
            receiver = function_node.child_by_field_name("object")
            if not args and receiver is not None:
                field = field_name_from_node(
                    self.source,
                    receiver,
                    self.aliases,
                    self.module_vars,
                )
                if field and field in self.signal_group_fields:
                    record_resource(self.tracker.signal_groups, field)
        elif call_name in SOURCE_REMOVE_NAMES:
            for arg in args:
                field = field_name_from_node(
                    self.source,
                    arg,
                    self.aliases,
                    self.module_vars,
                )
                if field:
                    record_resource(self.tracker.sources, field)
                elif arg.type == "identifier":
                    name = identifier_name(self.source, arg)
                    if name and self.aliases.get(name, "").startswith("group:source:"):
                        record_resource(
                            self.tracker.source_groups,
                            self.aliases[name].split(":", 2)[2],
                        )


def is_signal_connect_call(source: str, node: Node) -> bool:
    function_node = node.child_by_field_name("function")
    if function_node is None:
        return False

    if function_node.type != "member_expression":
        return False

    object_node = function_node.child_by_field_name("object")
    if object_node is not None and object_node.type == "this":
        return False

    call_name = ".".join(call_callee_parts(source, node))
    return call_name.endswith(".connect") or call_name.endswith(".connect_after")


def iter_immediate_nodes(node: Node):
    yield node

    if node.type in NON_IMMEDIATE_EXECUTION_NODES:
        return

    for child in node.children:
        if child.type in NON_IMMEDIATE_EXECUTION_NODES:
            continue

        yield from iter_immediate_nodes(child)


def method_reachability(
    source: str,
    methods: dict[str, list[Node]],
    start_names: list[str],
) -> list[Node]:
    result: list[Node] = []
    seen: set[str] = set()
    pending = list(start_names)

    while pending:
        name = pending.pop()
        if name in seen:
            continue

        seen.add(name)

        for method in methods.get(name, []):
            result.append(method)
            body = method.child_by_field_name("body")
            if body is None:
                continue

            for called_name in direct_this_method_calls(source, body):
                if called_name in methods:
                    pending.append(called_name)

            for called_name in direct_identifier_calls(source, body):
                if called_name in methods:
                    pending.append(called_name)

            for called_name in callback_identifier_arguments(source, body):
                if called_name in methods:
                    pending.append(called_name)

            for called_name in bound_this_callback_methods(source, body):
                if called_name in methods:
                    pending.append(called_name)

    return result


def resource_from_node(
    source: str,
    node: Node,
    aliases: dict[str, str],
    destroyable_classes: set[str],
) -> str | None:
    if node.type == "call_expression":
        if is_signal_connect_call(source, node):
            return "signal"

        call_name = ".".join(call_callee_parts(source, node))
        if call_name in SOURCE_ADD_NAMES:
            return "source"

        if call_name in RESOURCE_REF_CALL_NAMES:
            return "resource_ref"

        if call_name.endswith(".getSettings") or call_name == "getSettings":
            return "resource_ref"
    elif node.type == "new_expression":
        constructor = node.child_by_field_name("constructor")
        if constructor is not None:
            constructor_parts = member_expression_parts(source, constructor)
            constructor_name = ".".join(constructor_parts)
            if constructor_name in JS_BUILTIN_CONTAINERS:
                return "container"
            if constructor_name in SIGNAL_MANAGER_NEW_NAMES:
                return "signal_manager"
            if constructor_name in RESOURCE_REF_NEW_NAMES:
                return "resource_ref"
            if constructor_parts and (
                constructor_parts[0] in DESTROYABLE_NAMESPACE_ROOTS
                or constructor_name in destroyable_classes
            ):
                return "object"
    elif node.type in {"array", "object"}:
        return "container"
    elif node.type == "identifier":
        name = identifier_name(source, node)
        if name:
            return aliases.get(name)

    return None


def collect_destroyable_class_names(source: str, root: Node) -> set[str]:
    classes: set[str] = set()
    changed = True

    while changed:
        changed = False

        for node in iter_nodes(root):
            if node.type not in {"class", "class_declaration"}:
                continue

            name_node = node.child_by_field_name("name")
            superclass = node.child_by_field_name("superclass")
            if superclass is None:
                heritage = child_by_type(node, "class_heritage")
                if heritage is not None and heritage.named_children:
                    superclass = heritage.named_children[0]
            if superclass is None:
                continue

            name = node_text(source, name_node) if name_node is not None else None
            if name is None:
                parent = node.parent
                while parent is not None and parent.type != "variable_declarator":
                    parent = parent.parent

                if parent is not None:
                    declarator_name = parent.child_by_field_name("name")
                    name = identifier_name(source, declarator_name)

            if name is None or name in classes:
                continue

            superclass_parts = member_expression_parts(source, superclass)
            superclass_name = ".".join(superclass_parts)
            if not superclass_parts:
                continue

            if (
                superclass_parts[0] in DESTROYABLE_NAMESPACE_ROOTS
                or superclass_name in DESTROYABLE_SUPERCLASS_NAMES
                or (
                    len(superclass_parts) == 1
                    and superclass_parts[0] in DESTROYABLE_SUPERCLASS_NAMES
                )
                or superclass_name in classes
                or (len(superclass_parts) == 1 and superclass_parts[0] in classes)
            ):
                classes.add(name)
                changed = True

    return classes


def field_name_from_node(
    source: str,
    node: Node,
    aliases: dict[str, str] | None = None,
    module_vars: set[str] | None = None,
) -> str | None:
    field = member_expression_property(source, node)
    if field:
        return field

    return _resolved_identifier_field(source, node, aliases, None, module_vars)


def _resolved_identifier_field(
    source: str,
    node: Node,
    aliases: dict[str, str] | None = None,
    owner_aliases: dict[str, str] | None = None,
    module_vars: set[str] | None = None,
) -> str | None:
    aliases = aliases or {}
    owner_aliases = owner_aliases or {}
    module_vars = module_vars or set()

    if node.type == "identifier":
        name = identifier_name(source, node)
        if name:
            if name in owner_aliases:
                return owner_aliases[name]

            alias = aliases.get(name)
            if alias and alias.startswith("field:"):
                return alias.split(":", 1)[1]
            if name in module_vars:
                return name

    parts = member_expression_parts(source, node)
    if not parts:
        return None

    if len(parts) >= 2 and parts[0] == "this":
        return parts[1]

    if parts[0] in module_vars:
        return parts[0]

    return None


def owner_field_from_node(
    source: str,
    node: Node,
    aliases: dict[str, str] | None = None,
    owner_aliases: dict[str, str] | None = None,
    module_vars: set[str] | None = None,
) -> str | None:
    return _resolved_identifier_field(
        source,
        node,
        aliases,
        owner_aliases,
        module_vars,
    )


def is_release_value(source: str, node: Node) -> bool:
    if node.type == "null":
        return True

    if node.type == "identifier" and identifier_name(source, node) == "undefined":
        return True

    if node.type == "array" and not node.named_children:
        return True

    if node.type == "object" and not node.named_children:
        return True

    return False
