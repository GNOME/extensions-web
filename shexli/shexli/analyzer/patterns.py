# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass

from ..ast import (
    iter_nodes,
    member_expression_parts,
    node_text,
)
from .spawn import extract_literal_string


@dataclass(slots=True)
class StringPattern:
    parts: list[str | None]

    @property
    def exact(self) -> str | None:
        if any(part is None for part in self.parts):
            return None

        return "".join(part for part in self.parts if part is not None)

    @property
    def prefix(self) -> str:
        chunks: list[str] = []
        for part in self.parts:
            if part is None:
                break

            chunks.append(part)

        return "".join(chunks)

    @property
    def suffix(self) -> str:
        chunks: list[str] = []
        for part in reversed(self.parts):
            if part is None:
                break

            chunks.append(part)

        return "".join(reversed(chunks))


def concat_patterns(
    left: StringPattern | None,
    right: StringPattern | None,
) -> StringPattern | None:
    if left is None or right is None:
        return None

    parts = left.parts + right.parts
    normalized: list[str | None] = []

    for part in parts:
        if part is None:
            if normalized and normalized[-1] is None:
                continue

            normalized.append(None)
            continue

        if normalized and normalized[-1] is not None:
            normalized[-1] += part
            continue

        normalized.append(part)

    return StringPattern(normalized)


def pattern_from_literal(value: str) -> StringPattern:
    return StringPattern([value])


def getter_patterns_in_program(
    source: str,
    methods: dict[str, list],
    const_patterns: dict[str, StringPattern],
) -> dict[str, StringPattern]:
    patterns: dict[str, StringPattern] = {}

    for name, method_nodes in methods.items():
        for method in method_nodes:
            body = method.child_by_field_name("body")
            if body is None:
                continue

            statements = [
                child
                for child in body.named_children
                if child.type == "return_statement"
            ]
            if len(statements) != 1:
                continue

            value = statements[0].child_by_field_name("argument")
            if value is None and statements[0].named_children:
                value = statements[0].named_children[0]
            if value is None:
                continue

            pattern = evaluate_string_pattern(source, value, const_patterns, {})
            if pattern is not None:
                patterns[name] = pattern
                break

    return patterns


def const_patterns_in_program(
    source: str,
    root,
    getter_patterns: dict[str, StringPattern],
) -> dict[str, StringPattern]:
    patterns: dict[str, StringPattern] = {}

    changed = True
    while changed:
        changed = False

        for node in iter_nodes(root):
            if node.type != "variable_declarator":
                continue

            name_node = node.child_by_field_name("name")
            value_node = node.child_by_field_name("value")
            if name_node is None or value_node is None:
                continue

            name = node_text(source, name_node)
            if name in patterns:
                continue

            pattern = evaluate_string_pattern(
                source,
                value_node,
                patterns,
                getter_patterns,
            )
            if pattern is None:
                continue

            patterns[name] = pattern
            changed = True

    return patterns


def evaluate_string_pattern(
    source: str,
    node,
    const_patterns: dict[str, StringPattern],
    getter_patterns: dict[str, StringPattern],
) -> StringPattern | None:
    literal = extract_literal_string(source, node)
    if literal is not None:
        return pattern_from_literal(literal)

    if node.type == "template_string":
        pattern = pattern_from_literal("")
        for child in node.children:
            if child.type == "string_fragment":
                pattern = concat_patterns(
                    pattern,
                    pattern_from_literal(node_text(source, child)),
                )
            elif child.type == "template_substitution":
                expression = child.named_children[0] if child.named_children else None
                if expression is None:
                    return None

                expression_pattern = evaluate_string_pattern(
                    source,
                    expression,
                    const_patterns,
                    getter_patterns,
                )
                if expression_pattern is None:
                    expression_pattern = StringPattern([None])

                pattern = concat_patterns(pattern, expression_pattern)

        return pattern

    if node.type == "binary_expression":
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        operator = node.child_by_field_name("operator")
        if (
            left is None
            or right is None
            or operator is None
            or node_text(source, operator) != "+"
        ):
            return None

        return concat_patterns(
            evaluate_string_pattern(source, left, const_patterns, getter_patterns),
            evaluate_string_pattern(source, right, const_patterns, getter_patterns),
        )

    if node.type == "identifier":
        return const_patterns.get(node_text(source, node))

    if node.type == "member_expression":
        parts = member_expression_parts(source, node)
        if len(parts) == 2 and parts[0] == "this":
            return getter_patterns.get(parts[1])

    return None
