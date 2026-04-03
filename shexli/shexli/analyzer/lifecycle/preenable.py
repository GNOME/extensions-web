# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from pathlib import Path

from tree_sitter import Node

from ...ast import (
    call_callee_parts,
    member_expression_parts,
    top_level_class_names,
    top_level_statements,
)
from ...models import Evidence
from ..evidence import node_evidence
from ..paths import PathMapper
from .base import (
    SOURCE_ADD_NAMES,
    TOP_LEVEL_FORBIDDEN_NEW_PREFIXES,
    iter_immediate_nodes,
    method_reachability,
    resource_from_node,
)


def collect_pre_enable_evidence(
    source: str,
    path: Path,
    root: Node,
    methods: dict[str, list[Node]],
    mapper: PathMapper,
) -> list[Evidence]:
    local_class_names = top_level_class_names(source, root)
    bodies: list[Node] = []

    for node in top_level_statements(root):
        if node.type in {"import_statement", "export_statement", "class_declaration"}:
            continue

        bodies.append(node)

    if path.name not in {"extension.js", "prefs.js"}:
        return _pre_enable_evidence(
            source,
            path,
            mapper,
            local_class_names,
            bodies,
        )

    constructor_reachable = method_reachability(
        source,
        methods,
        ["constructor", "_init"],
    )
    for method in constructor_reachable:
        body = method.child_by_field_name("body")
        if body is not None:
            bodies.append(body)

    return _pre_enable_evidence(
        source,
        path,
        mapper,
        local_class_names,
        bodies,
    )


def _pre_enable_evidence(
    source: str,
    path: Path,
    mapper: PathMapper,
    local_class_names: set[str],
    bodies: list[Node],
) -> list[Evidence]:
    evidence: list[Evidence] = []

    for body in bodies:
        for sub in iter_immediate_nodes(body):
            if sub.type == "new_expression":
                constructor = sub.child_by_field_name("constructor")
                if constructor is None:
                    continue

                parts = member_expression_parts(source, constructor)
                if parts and (
                    parts[0] in TOP_LEVEL_FORBIDDEN_NEW_PREFIXES
                    or (len(parts) == 1 and parts[0] in local_class_names)
                ):
                    evidence.append(node_evidence(path, source, sub, mapper))
            elif sub.type == "call_expression":
                call_name = ".".join(call_callee_parts(source, sub))
                if call_name.endswith(".connect") or call_name in SOURCE_ADD_NAMES:
                    evidence.append(node_evidence(path, source, sub, mapper))
            elif sub.type == "variable_declarator":
                value = sub.child_by_field_name("value")
                kind = (
                    resource_from_node(
                        source,
                        value,
                        {},
                        local_class_names,
                    )
                    if value is not None
                    else None
                )
                if kind in {"object", "resource_ref", "signal", "source"}:
                    evidence.append(node_evidence(path, source, sub, mapper))
            elif sub.type == "assignment_expression":
                right = sub.child_by_field_name("right")
                kind = (
                    resource_from_node(
                        source,
                        right,
                        {},
                        local_class_names,
                    )
                    if right is not None
                    else None
                )
                if kind in {"object", "resource_ref", "signal", "source"}:
                    evidence.append(node_evidence(path, source, sub, mapper))

    return evidence
