# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from tree_sitter import Node

from ...ast import (
    call_arguments,
    call_callee_parts,
    default_export_class_methods,
    iter_nodes,
    legacy_entrypoint_methods,
    member_expression_parts,
    node_text,
    top_level_function_methods,
)
from ...spec import R
from ..context import CheckContext
from ..engine import FileRule
from ..lifecycle import method_reachability


def _retained_field_name(text: str, node) -> str | None:
    if node.type != "assignment_expression":
        return None
    left = node.child_by_field_name("left")
    if left is None:
        return None
    parts = member_expression_parts(text, left)
    if len(parts) == 2 and parts[0] == "this":
        return parts[1]
    return None


def _retained_value_node(node):
    if node.type != "assignment_expression":
        return None
    return node.child_by_field_name("right")


def _retains_window_objects(
    text: str,
    methods: dict[str, list],
    ctx: CheckContext,
) -> list:
    retained_evidences = []
    fill_methods = method_reachability(text, methods, ["fillPreferencesWindow"])
    if not fill_methods:
        return retained_evidences

    has_close_request_cleanup = False
    for method in fill_methods:
        body = method.child_by_field_name("body")
        if body is None:
            continue

        for node in iter_nodes(body):
            if node.type == "call_expression":
                call_name = ".".join(call_callee_parts(text, node))
                if call_name.endswith(".connect"):
                    args = call_arguments(node)
                    if (
                        len(args) >= 2
                        and args[0].type == "string"
                        and node_text(text, args[0]).strip("\"'") == "close-request"
                    ):
                        has_close_request_cleanup = True

            field = _retained_field_name(text, node)
            if not field:
                continue

            value = _retained_value_node(node)
            if value is None or value.type not in {"new_expression", "call_expression"}:
                continue

            retained_evidences.append(ctx.node_evidence(text, node))

    if has_close_request_cleanup:
        return []

    return retained_evidences


class PrefsRule(FileRule):
    """FileRule: EGO032/EGO033 — getPreferencesWidget and retained prefs fields."""

    def __init__(self, metadata: dict | None) -> None:
        self._metadata = metadata

    def check(self, root: Node, text: str, ctx: CheckContext) -> None:
        if ctx.path.name != "prefs.js":
            return

        methods = default_export_class_methods(text, root) or legacy_entrypoint_methods(
            text, root
        )
        top_level_methods = top_level_function_methods(text, root)

        if ctx.path.name in {"extension.js", "prefs.js"}:
            for name, nodes in top_level_methods.items():
                methods.setdefault(name, []).extend(nodes)

        if any(version >= 45 for version in ctx.target_versions):
            prefs_widget_evidences = []
            for method in methods.get(
                "getPreferencesWidget", []
            ) or top_level_methods.get("getPreferencesWidget", []):
                prefs_widget_evidences.append(ctx.node_evidence(text, method))

            if prefs_widget_evidences:
                ctx.add_finding(
                    R.EGO032,
                    (
                        "45+ preferences code should use `fillPreferencesWindow()` "
                        "instead of `getPreferencesWidget()`."
                    ),
                    prefs_widget_evidences,
                )

        retained_evidences = _retains_window_objects(text, methods, ctx)
        if retained_evidences:
            ctx.add_finding(
                R.EGO033,
                (
                    "Preferences code stores window-scoped objects on the "
                    "exported prefs class without `close-request` cleanup."
                ),
                retained_evidences[:10],
            )
