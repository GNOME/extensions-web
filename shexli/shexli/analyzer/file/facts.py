# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tree_sitter import Node

from ...ast import (
    JSImport,
    call_arguments,
    call_callee_parts,
    child_by_type,
    default_export_class_methods,
    identifier_name,
    imports_in_program,
    iter_nodes,
    legacy_entrypoint_methods,
    legacy_imports_in_program,
    member_expression_parts,
    node_text,
    top_level_function_methods,
)
from ..lifecycle.base import method_reachability
from ..spawn import SPAWN_CALL_NAMES
from .indices import CallIndex, spawn_argv_arg


@dataclass(slots=True)
class FunctionInfo:
    """Top-level function declaration fact."""

    name: str
    params: list[str]
    node: Node


@dataclass(slots=True)
class MethodInfo:
    """Class method declaration fact."""

    name: str
    params: list[str]
    node: Node


@dataclass(slots=True)
class ClassInfo:
    """Top-level class declaration fact."""

    name: str
    superclass_parts: list[tuple[str, ...]]
    methods: dict[str, MethodInfo]
    node: Node


@dataclass(frozen=True, slots=True)
class DeclarationIndex:
    """Top-level declaration facts available to rules."""

    functions: dict[str, FunctionInfo]
    classes: dict[str, ClassInfo]
    exports: dict[str, Node]


class DeclarationCollector:
    """Single-pass AST collector that builds a :class:`DeclarationIndex`."""

    def collect(self, source: str, root: Node) -> DeclarationIndex:
        functions: dict[str, FunctionInfo] = {}
        classes: dict[str, ClassInfo] = {}
        exports: dict[str, Node] = {}

        for child in root.children:
            if child.type == "function_declaration":
                _collect_function(source, child, functions)
            elif child.type == "class_declaration":
                _collect_class(source, child, classes)
            elif child.type == "export_statement":
                _collect_export(source, child, functions, classes, exports)

        return DeclarationIndex(functions=functions, classes=classes, exports=exports)


class ImportCollector:
    """Collector for all static import facts in a JS file."""

    def collect(self, source: str, root: Node) -> list[JSImport]:
        return imports_in_program(source, root) + legacy_imports_in_program(
            source,
            root,
        )


@dataclass(frozen=True, slots=True)
class PrefsFacts:
    """Derived facts used by :class:`PrefsRule`."""

    get_preferences_widget_nodes: list[Node]
    state_assignment_nodes: list[Node]
    close_request_cleanup_nodes: list[Node]


@dataclass(frozen=True, slots=True)
class SessionModesFacts:
    """Derived facts used by :class:`SessionModesRule`."""

    disable_method_nodes: list[Node]
    commented_disable_nodes: list[Node]


class IdentifierCollector:
    """Single-pass AST collector that returns all identifier names."""

    def collect(self, root: Node) -> list[str]:
        result: list[str] = []
        for node in iter_nodes(root):
            if node.type == "identifier" and node.text is not None:
                result.append(node.text.decode())
        return result


class PrefsFactsCollector:
    def collect(self, source: str, root: Node, path: Path) -> PrefsFacts:
        if path.name != "prefs.js":
            return PrefsFacts([], [], [])

        methods = self._entrypoint_methods(source, root, path)
        top_level_methods = top_level_function_methods(source, root)

        return PrefsFacts(
            get_preferences_widget_nodes=(
                methods.get("getPreferencesWidget", [])
                or top_level_methods.get("getPreferencesWidget", [])
            ),
            state_assignment_nodes=self._state_assignment_nodes(
                source,
                methods,
            ),
            close_request_cleanup_nodes=self._close_request_cleanup_nodes(
                source,
                methods,
            ),
        )

    def _entrypoint_methods(
        self,
        source: str,
        root: Node,
        path: Path,
    ) -> dict[str, list[Node]]:
        methods = default_export_class_methods(
            source, root
        ) or legacy_entrypoint_methods(source, root)

        if path.name in {"extension.js", "prefs.js"}:
            for name, nodes in top_level_function_methods(source, root).items():
                methods.setdefault(name, []).extend(nodes)

        return methods

    def _fill_preferences_methods(
        self,
        source: str,
        methods: dict[str, list[Node]],
    ) -> list[Node]:
        return method_reachability(source, methods, ["fillPreferencesWindow"])

    def _state_assignment_nodes(
        self,
        source: str,
        methods: dict[str, list[Node]],
    ) -> list[Node]:
        assignment_nodes: list[Node] = []
        for method in self._fill_preferences_methods(source, methods):
            body = method.child_by_field_name("body")
            if body is None:
                continue

            for node in iter_nodes(body):
                field = _retained_field_name(source, node)
                if not field:
                    continue

                value = _retained_value_node(node)
                if value is None or value.type not in {
                    "new_expression",
                    "call_expression",
                }:
                    continue

                assignment_nodes.append(node)

        return assignment_nodes

    def _close_request_cleanup_nodes(
        self,
        source: str,
        methods: dict[str, list[Node]],
    ) -> list[Node]:
        cleanup_nodes: list[Node] = []
        for method in self._fill_preferences_methods(source, methods):
            body = method.child_by_field_name("body")
            if body is None:
                continue

            for node in iter_nodes(body):
                if node.type != "call_expression":
                    continue
                call_name = ".".join(call_callee_parts(source, node))
                if not call_name.endswith(".connect"):
                    continue
                args = call_arguments(node)
                if (
                    len(args) >= 2
                    and args[0].type == "string"
                    and node_text(source, args[0]).strip("\"'") == "close-request"
                ):
                    cleanup_nodes.append(node)

        return cleanup_nodes


class SessionModesFactsCollector:
    def collect(self, source: str, root: Node, path: Path) -> SessionModesFacts:
        if path.name != "extension.js":
            return SessionModesFacts(
                disable_method_nodes=[], commented_disable_nodes=[]
            )

        methods = default_export_class_methods(
            source, root
        ) or legacy_entrypoint_methods(source, root)
        disable_methods = method_reachability(source, methods, ["disable"])
        commented_disable_nodes = [
            comment_node
            for method in disable_methods
            if (comment_node := self._disable_comment_node(source, method)) is not None
        ]
        return SessionModesFacts(
            disable_method_nodes=disable_methods,
            commented_disable_nodes=commented_disable_nodes,
        )

    def _disable_comment_node(self, source: str, method: Node) -> Node | None:
        comment_node = method.prev_named_sibling
        if (
            comment_node is not None
            and comment_node.type == "comment"
            and self._is_session_comment(source, comment_node)
        ):
            return comment_node

        body = method.child_by_field_name("body")
        if body is None:
            return None

        for child in body.named_children:
            if child.type == "comment" and self._is_session_comment(source, child):
                return child
            return None

        return None

    def _is_session_comment(self, source: str, comment_node: Node) -> bool:
        comment_text = node_text(source, comment_node).lower()
        return "session" in comment_text or "unlock" in comment_text


class StylesheetBindingCollector:
    def collect(self, source: str, calls: CallIndex) -> frozenset[str]:
        bindings: set[str] = set()
        for site in calls.find_suffix("get_child"):
            if not site.arg_literals:
                continue
            if site.arg_literals[0] != "stylesheet.css":
                continue
            parent = site.node.parent
            if parent is None or parent.type != "variable_declarator":
                continue
            name_node = parent.child_by_field_name("name")
            binding = identifier_name(source, name_node) if name_node else None
            if binding:
                bindings.add(binding)
        return frozenset(bindings)


class SpawnWrapperCollector:
    def collect(self, source: str, declarations: DeclarationIndex) -> frozenset[str]:
        wrappers: set[str] = set()
        for name, func in declarations.functions.items():
            if self._is_wrapper(source, func):
                wrappers.add(name)
        return frozenset(wrappers)

    def _is_wrapper(self, source: str, func: FunctionInfo) -> bool:
        if not func.params:
            return False
        argv_param = func.params[0]
        body = func.node.child_by_field_name("body")
        if body is None:
            return False
        for node in iter_nodes(body):
            if node.type != "call_expression":
                continue
            call_name = ".".join(call_callee_parts(source, node))
            if call_name not in SPAWN_CALL_NAMES:
                continue
            args = call_arguments(node)
            argv_arg = spawn_argv_arg(call_name, args)
            if argv_arg is None or argv_arg.type != "identifier":
                continue
            if identifier_name(source, argv_arg) == argv_param:
                return True
        return False


def _retained_field_name(source: str, node: Node) -> str | None:
    if node.type != "assignment_expression":
        return None
    left = node.child_by_field_name("left")
    if left is None:
        return None
    parts = member_expression_parts(source, left)
    if len(parts) == 2 and parts[0] == "this":
        return parts[1]
    return None


def _retained_value_node(node: Node) -> Node | None:
    if node.type != "assignment_expression":
        return None
    return node.child_by_field_name("right")


def _collect_params(source: str, node: Node | None) -> list[str]:
    if node is None or node.type != "formal_parameters":
        return []
    result: list[str] = []
    for child in node.named_children:
        if child.type == "identifier":
            result.append(node_text(source, child))
        elif child.type == "assignment_pattern":
            left = child.child_by_field_name("left")
            if left is not None and left.type == "identifier":
                result.append(node_text(source, left))
    return result


def _collect_function(
    source: str,
    node: Node,
    out: dict[str, FunctionInfo],
) -> FunctionInfo | None:
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None
    name = node_text(source, name_node)
    info = FunctionInfo(
        name=name,
        params=_collect_params(source, node.child_by_field_name("parameters")),
        node=node,
    )
    out[name] = info
    return info


def _collect_methods_from_body(
    source: str,
    class_body: Node,
) -> dict[str, MethodInfo]:
    methods: dict[str, MethodInfo] = {}
    for child in class_body.named_children:
        if child.type != "method_definition":
            continue
        name_node = child.child_by_field_name("name")
        if name_node is None:
            continue
        name = node_text(source, name_node)
        info = MethodInfo(
            name=name,
            params=_collect_params(source, child.child_by_field_name("parameters")),
            node=child,
        )
        methods[name] = info
    return methods


def _collect_class(
    source: str,
    node: Node,
    out: dict[str, ClassInfo],
) -> ClassInfo | None:
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None
    name = node_text(source, name_node)

    superclass_parts: list[tuple[str, ...]] = []
    superclass = node.child_by_field_name("superclass")
    if superclass is None:
        heritage = child_by_type(node, "class_heritage")
        if heritage is not None and heritage.named_children:
            superclass = heritage.named_children[0]
    if superclass is not None:
        parts = tuple(member_expression_parts(source, superclass))
        if parts:
            superclass_parts.append(parts)

    class_body = child_by_type(node, "class_body")
    methods = _collect_methods_from_body(source, class_body) if class_body else {}

    info = ClassInfo(
        name=name,
        superclass_parts=superclass_parts,
        methods=methods,
        node=node,
    )
    out[name] = info
    return info


def _collect_export(
    source: str,
    stmt: Node,
    functions: dict[str, FunctionInfo],
    classes: dict[str, ClassInfo],
    exports: dict[str, Node],
) -> None:
    is_default = any(child.type == "default" for child in stmt.children)
    for child in stmt.named_children:
        if child.type == "function_declaration":
            info = _collect_function(source, child, functions)
            if info is not None:
                exports.setdefault("default" if is_default else info.name, child)
        elif child.type in {"class", "class_declaration"}:
            info = _collect_class(source, child, classes)
            if info is not None:
                exports.setdefault("default" if is_default else info.name, child)
