# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass

import tree_sitter_javascript as tsjs
from tree_sitter import Language, Node, Parser

JS_LANGUAGE = Language(tsjs.language())
PARSER = Parser(JS_LANGUAGE)


@dataclass(slots=True)
class JSImport:
    module: str | None
    names: list[str]
    line: int
    snippet: str


@dataclass(slots=True)
class JSCall:
    callee: str
    line: int
    snippet: str


def parse_js(source: str):
    return PARSER.parse(source.encode("utf-8"))


def node_text(source: str, node: Node) -> str:
    return source.encode("utf-8")[node.start_byte : node.end_byte].decode("utf-8")


def iter_nodes(node: Node):
    yield node
    for child in node.children:
        yield from iter_nodes(child)


def child_by_type(node: Node, node_type: str) -> Node | None:
    for child in node.children:
        if child.type == node_type:
            return child
    return None


def identifier_name(source: str, node: Node | None) -> str | None:
    if node is None:
        return None
    if node.type in {
        "identifier",
        "property_identifier",
        "private_property_identifier",
    }:
        return node_text(source, node)
    return None


def pattern_bound_names(source: str, node: Node | None) -> list[str]:
    if node is None:
        return []

    if node.type in {
        "identifier",
        "property_identifier",
        "private_property_identifier",
        "shorthand_property_identifier_pattern",
    }:
        return [node_text(source, node)]

    names: list[str] = []
    for child in node.named_children:
        names.extend(pattern_bound_names(source, child))

    return names


def member_expression_parts(source: str, node: Node) -> list[str]:
    if node.type == "identifier":
        return [node_text(source, node)]
    if node.type in {"property_identifier", "private_property_identifier"}:
        return [node_text(source, node)]
    if node.type == "this":
        return ["this"]
    if node.type == "member_expression":
        object_node = node.child_by_field_name("object")
        property_node = node.child_by_field_name("property")
        if object_node is None or property_node is None:
            return []
        return member_expression_parts(source, object_node) + member_expression_parts(
            source, property_node
        )
    if node.type == "subscript_expression":
        return [node_text(source, node)]
    return []


def member_expression_property(source: str, node: Node) -> str | None:
    parts = member_expression_parts(source, node)
    if len(parts) == 2 and parts[0] == "this":
        return parts[1]
    return None


def call_callee_parts(source: str, node: Node) -> list[str]:
    if node.type != "call_expression":
        return []
    function_node = node.child_by_field_name("function")
    if function_node is None:
        return []
    return member_expression_parts(source, function_node)


def assignment_target_this_property(source: str, node: Node) -> str | None:
    if node.type != "assignment_expression":
        return None
    left = node.child_by_field_name("left")
    if left is None:
        return None
    parts = member_expression_parts(source, left)
    if len(parts) == 2 and parts[0] == "this":
        return parts[1]
    return None


def variable_declarator_name(source: str, node: Node) -> str | None:
    if node.type != "variable_declarator":
        return None
    return identifier_name(source, node.child_by_field_name("name"))


def variable_declarator_value(node: Node) -> Node | None:
    if node.type != "variable_declarator":
        return None
    return node.child_by_field_name("value")


def assigned_call_name(source: str, node: Node) -> list[str]:
    if node.type != "assignment_expression":
        return []
    right = node.child_by_field_name("right")
    if right is None or right.type != "call_expression":
        return []
    return call_callee_parts(source, right)


def assigned_new_target(source: str, node: Node) -> list[str]:
    if node.type != "assignment_expression":
        return []
    right = node.child_by_field_name("right")
    if right is None or right.type != "new_expression":
        return []
    constructor = right.child_by_field_name("constructor")
    if constructor is None:
        return []
    return member_expression_parts(source, constructor)


def imports_in_program(source: str, root: Node) -> list[JSImport]:
    imports: list[JSImport] = []
    for child in root.children:
        if child.type not in {"import_statement", "export_statement"}:
            continue
        snippet = node_text(source, child)
        module = None
        names: list[str] = []
        for sub in child.children:
            if sub.type == "string":
                module = node_text(source, sub).strip("\"'")
            elif sub.type in {"identifier", "namespace_import", "named_imports"}:
                names.append(node_text(source, sub))
        imports.append(
            JSImport(
                module=module,
                names=names,
                line=child.start_point.row + 1,
                snippet=snippet,
            )
        )
    return imports


def legacy_imports_in_program(source: str, root: Node) -> list[JSImport]:
    imports: list[JSImport] = []
    seen: set[tuple[int, str, str]] = set()

    for node in iter_nodes(root):
        if node.type == "variable_declarator":
            name_node = node.child_by_field_name("name")
            value_node = node.child_by_field_name("value")
            if name_node is None or value_node is None:
                continue

            value_parts = member_expression_parts(source, value_node)
            if value_parts == ["imports", "gi"]:
                for name in pattern_bound_names(source, name_node):
                    key = (node.start_point.row + 1, f"gi://{name}", name)
                    if key in seen:
                        continue

                    seen.add(key)
                    imports.append(
                        JSImport(
                            module=f"gi://{name}",
                            names=[name],
                            line=node.start_point.row + 1,
                            snippet=node_text(source, node),
                        )
                    )

            if len(value_parts) >= 2 and value_parts[0] == "imports":
                module = ".".join(value_parts)
                bound_names = pattern_bound_names(source, name_node)
                if not bound_names:
                    bound_names = [value_parts[-1]]

                for name in bound_names:
                    key = (node.start_point.row + 1, module, name)
                    if key in seen:
                        continue

                    seen.add(key)
                    imports.append(
                        JSImport(
                            module=module,
                            names=[name],
                            line=node.start_point.row + 1,
                            snippet=node_text(source, node),
                        )
                    )

        if node.type != "member_expression":
            continue

        parts = member_expression_parts(source, node)
        if len(parts) < 2 or parts[0] != "imports":
            continue

        if parts[1] not in {"byteArray", "lang", "mainloop"}:
            continue

        module = ".".join(parts[:2])
        name = parts[1]
        key = (node.start_point.row + 1, module, name)
        if key in seen:
            continue

        seen.add(key)
        imports.append(
            JSImport(
                module=module,
                names=[name],
                line=node.start_point.row + 1,
                snippet=node_text(source, node),
            )
        )

    return imports


def dynamic_imports_in_program(source: str, root: Node) -> list[JSImport]:
    imports: list[JSImport] = []

    for node in iter_nodes(root):
        if node.type != "call_expression":
            continue

        function_node = node.child_by_field_name("function")
        if function_node is None or function_node.type != "import":
            continue

        arguments = call_arguments(node)
        if len(arguments) != 1 or arguments[0].type != "string":
            continue

        imports.append(
            JSImport(
                module=node_text(source, arguments[0]).strip("\"'"),
                names=[],
                line=node.start_point.row + 1,
                snippet=node_text(source, node),
            )
        )

    return imports


def top_level_statements(root: Node) -> list[Node]:
    return [child for child in root.children if child.is_named]


def class_methods(source: str, root: Node) -> dict[str, list[Node]]:
    methods: dict[str, list[Node]] = {}
    for node in iter_nodes(root):
        if node.type != "method_definition":
            continue
        name_node = node.child_by_field_name("name")
        if name_node is None:
            continue
        name = node_text(source, name_node)
        methods.setdefault(name, []).append(node)
    return methods


def default_export_class_methods(source: str, root: Node) -> dict[str, list[Node]]:
    for child in root.children:
        if child.type != "export_statement":
            continue

        class_node = None
        for sub in child.named_children:
            if sub.type in {"class", "class_declaration"}:
                class_node = sub
                break

        if class_node is None:
            continue

        return _methods_from_class_node(source, class_node)

    return {}


def _methods_from_class_node(source: str, class_node: Node) -> dict[str, list[Node]]:
    methods: dict[str, list[Node]] = {}
    class_body = child_by_type(class_node, "class_body")
    if class_body is None:
        return methods

    for node in class_body.named_children:
        if node.type != "method_definition":
            continue

        name_node = node.child_by_field_name("name")
        if name_node is None:
            continue

        name = node_text(source, name_node)
        methods.setdefault(name, []).append(node)

    return methods


def _top_level_classes(source: str, root: Node) -> dict[str, dict[str, list[Node]]]:
    classes: dict[str, dict[str, list[Node]]] = {}

    for child in root.children:
        if child.type == "class_declaration":
            name_node = child.child_by_field_name("name")
            if name_node is None:
                continue

            classes[node_text(source, name_node)] = _methods_from_class_node(
                source, child
            )
            continue

        if child.type not in {"lexical_declaration", "variable_declaration"}:
            continue

        for declarator in child.named_children:
            if declarator.type != "variable_declarator":
                continue

            name_node = declarator.child_by_field_name("name")
            value_node = declarator.child_by_field_name("value")
            if name_node is None or value_node is None:
                continue

            class_node = None
            if value_node.type in {"class", "class_declaration"}:
                class_node = value_node
            elif value_node.type in {"call_expression", "new_expression"}:
                for argument in call_arguments(value_node):
                    if argument.type in {"class", "class_declaration"}:
                        class_node = argument
                        break

            if class_node is None:
                continue

            classes[node_text(source, name_node)] = _methods_from_class_node(
                source,
                class_node,
            )

    return classes


def legacy_entrypoint_methods(source: str, root: Node) -> dict[str, list[Node]]:
    methods: dict[str, list[Node]] = {}

    for child in root.children:
        if child.type != "function_declaration":
            continue

        name_node = child.child_by_field_name("name")
        if name_node is None:
            continue

        name = node_text(source, name_node)
        methods.setdefault(name, []).append(child)

    if "enable" in methods or "disable" in methods:
        return methods

    classes = _top_level_classes(source, root)
    if not classes:
        return {}

    for child in root.children:
        if child.type != "function_declaration":
            continue

        name_node = child.child_by_field_name("name")
        body = child.child_by_field_name("body")
        if name_node is None or body is None or node_text(source, name_node) != "init":
            continue

        for node in iter_nodes(body):
            if node.type != "return_statement":
                continue

            argument = node.child_by_field_name("argument")
            if argument is None and node.named_children:
                argument = node.named_children[0]
            if argument is None or argument.type != "new_expression":
                continue

            constructor = argument.child_by_field_name("constructor")
            if constructor is None:
                continue

            constructor_name = node_text(source, constructor)
            if constructor_name in classes:
                return classes[constructor_name]

    return {}


def top_level_variable_names(source: str, root: Node) -> set[str]:
    names: set[str] = set()

    for child in root.children:
        if child.type not in {"lexical_declaration", "variable_declaration"}:
            continue

        for declarator in child.named_children:
            if declarator.type != "variable_declarator":
                continue

            name_node = declarator.child_by_field_name("name")
            if name_node is not None and name_node.type == "identifier":
                names.add(node_text(source, name_node))

    return names


def top_level_class_names(source: str, root: Node) -> set[str]:
    return set(_top_level_classes(source, root))


def top_level_class_methods(
    source: str, root: Node
) -> dict[str, dict[str, list[Node]]]:
    return _top_level_classes(source, root)


def top_level_function_methods(source: str, root: Node) -> dict[str, list[Node]]:
    methods: dict[str, list[Node]] = {}

    for child in root.children:
        if child.type != "function_declaration":
            continue

        name_node = child.child_by_field_name("name")
        if name_node is None:
            continue

        methods.setdefault(node_text(source, name_node), []).append(child)

    return methods


def direct_this_method_calls(source: str, node: Node) -> list[str]:
    names: list[str] = []
    for sub in iter_nodes(node):
        if sub.type != "call_expression":
            continue
        function_node = sub.child_by_field_name("function")
        if function_node is None:
            continue
        parts = member_expression_parts(source, function_node)
        if len(parts) == 2 and parts[0] == "this":
            names.append(parts[1])
    return names


def direct_identifier_calls(source: str, node: Node) -> list[str]:
    names: list[str] = []
    for sub in iter_nodes(node):
        if sub.type != "call_expression":
            continue

        function_node = sub.child_by_field_name("function")
        if function_node is None or function_node.type != "identifier":
            continue

        names.append(node_text(source, function_node))

    return names


def callback_identifier_arguments(source: str, node: Node) -> list[str]:
    names: list[str] = []
    for sub in iter_nodes(node):
        if sub.type != "call_expression":
            continue

        parts = call_callee_parts(source, sub)
        call_name = ".".join(parts)
        if not (call_name.endswith(".connect") or call_name.endswith(".connectObject")):
            continue

        for argument in call_arguments(sub):
            if argument.type == "identifier":
                names.append(node_text(source, argument))

    return names


def bound_this_callback_methods(source: str, node: Node) -> list[str]:
    names: list[str] = []
    for sub in iter_nodes(node):
        if sub.type != "call_expression":
            continue

        function_node = sub.child_by_field_name("function")
        if function_node is None:
            continue

        parts = member_expression_parts(source, function_node)
        if len(parts) != 2 or parts[1] != "bind":
            continue

        target = function_node.child_by_field_name("object")
        if target is None:
            continue

        target_parts = member_expression_parts(source, target)
        if len(target_parts) != 2 or target_parts[0] != "this":
            continue

        args = call_arguments(sub)
        if len(args) != 1 or args[0].type != "this":
            continue

        names.append(target_parts[1])

    return names


def connect_bound_this_callback_methods(source: str, node: Node) -> list[str]:
    names: list[str] = []
    for sub in iter_nodes(node):
        if sub.type != "call_expression":
            continue

        call_name = ".".join(call_callee_parts(source, sub))
        if not (call_name.endswith(".connect") or call_name.endswith(".connectObject")):
            continue

        for argument in call_arguments(sub):
            if argument.type != "call_expression":
                continue

            function_node = argument.child_by_field_name("function")
            if function_node is None:
                continue

            parts = member_expression_parts(source, function_node)
            if len(parts) != 3 or parts[2] != "bind":
                continue

            target = function_node.child_by_field_name("object")
            if target is None:
                continue

            target_parts = member_expression_parts(source, target)
            if len(target_parts) != 2 or target_parts[0] != "this":
                continue

            args = call_arguments(argument)
            if len(args) != 1 or args[0].type != "this":
                continue

            names.append(target_parts[1])

    return names


def connect_callback_methods_for_events(
    source: str,
    node: Node,
    events: set[str],
) -> list[str]:
    names: list[str] = []
    for sub in iter_nodes(node):
        if sub.type != "call_expression":
            continue

        call_name = ".".join(call_callee_parts(source, sub))
        if not (call_name.endswith(".connect") or call_name.endswith(".connectObject")):
            continue

        arguments = call_arguments(sub)
        if not arguments or arguments[0].type != "string":
            continue

        event_name = node_text(source, arguments[0]).strip("\"'")
        if event_name not in events:
            continue

        for argument in arguments[1:]:
            if argument.type == "identifier":
                names.append(node_text(source, argument))
                continue

            if argument.type != "call_expression":
                continue

            function_node = argument.child_by_field_name("function")
            if function_node is None:
                continue

            parts = member_expression_parts(source, function_node)
            if len(parts) != 3 or parts[2] != "bind":
                continue

            target = function_node.child_by_field_name("object")
            if target is None:
                continue

            target_parts = member_expression_parts(source, target)
            if len(target_parts) != 2 or target_parts[0] != "this":
                continue

            bind_args = call_arguments(argument)
            if len(bind_args) != 1 or bind_args[0].type != "this":
                continue

            names.append(target_parts[1])

    return names


def call_arguments(node: Node) -> list[Node]:
    args = node.child_by_field_name("arguments")
    return list(args.named_children) if args is not None else []


def array_elements(node: Node) -> list[Node]:
    if node.type != "array":
        return []
    return list(node.named_children)
