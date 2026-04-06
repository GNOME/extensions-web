# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Callable

from tree_sitter import Node

from ...api_data import API
from ...ast import (
    call_arguments,
    call_callee_parts,
    iter_nodes,
    member_expression_parts,
)
from ...models import Evidence
from ...spec import R
from ..context import CheckContext
from ..engine import FileRule
from ..spawn import extract_literal_string

_GNOME49_SIGNAL_REMOVED_CLASSES = API.compat.gnome49.removed_clutter_classes
_GNOME50_REMOVED_DISPLAY_SIGNALS = API.compat.gnome50.removed_display_signals


def _append_removed_api_findings(
    ctx: CheckContext,
    text: str,
    root: Node,
    checks: list[tuple[str, str, Callable[[str, Node], bool]]],
) -> None:
    evidence_by_rule: dict[str, list[Evidence]] = {
        rule_id: [] for rule_id, _message, _matcher in checks
    }

    for node in iter_nodes(root):
        for rule_id, _message, matcher in checks:
            if matcher(text, node):
                evidence_by_rule[rule_id].append(ctx.node_evidence(text, node))

    for rule_id, message, _matcher in checks:
        evidences = evidence_by_rule[rule_id]
        if not evidences:
            continue
        ctx.add_finding(rule_id, message, evidences)


def _is_removed_clutter_action(source: str, node: Node) -> bool:
    if node.type != "new_expression":
        return False
    constructor = node.child_by_field_name("constructor")
    if constructor is None:
        return False
    constructor_name = ".".join(member_expression_parts(source, constructor))
    return constructor_name in _GNOME49_SIGNAL_REMOVED_CLASSES


def _uses_removed_maximize_flags(source: str, node: Node) -> bool:
    if node.type != "call_expression":
        return False
    call_name = ".".join(call_callee_parts(source, node))
    if not (
        call_name.endswith(".maximize")
        or call_name.endswith(".unmaximize")
        or call_name in {"maximize", "unmaximize"}
    ):
        return False
    return any(
        ".".join(member_expression_parts(source, arg)).startswith("Meta.MaximizeFlags")
        for arg in call_arguments(node)
    )


def _calls_removed_method(source: str, node: Node, suffixes: set[str]) -> bool:
    if node.type != "call_expression":
        return False
    call_name = ".".join(call_callee_parts(source, node))
    return any(call_name.endswith(s) or call_name == s for s in suffixes)


def _connects_removed_display_signal(source: str, node: Node) -> bool:
    if node.type != "call_expression":
        return False
    call_name = ".".join(call_callee_parts(source, node))
    if not (
        call_name.startswith("global.display.")
        and call_name.split(".")[-1] == "connect"
    ):
        return False
    args = call_arguments(node)
    if not args:
        return False
    signal = extract_literal_string(source, args[0])
    return signal in _GNOME50_REMOVED_DISPLAY_SIGNALS


class VersionCompatRule(FileRule):
    """FileRule: EGO_C49/EGO_C50 — removed APIs in targeted shell versions."""

    def __init__(self, js_imports: list) -> None:
        self._js_imports = js_imports

    def check(self, root: Node, text: str, ctx: CheckContext) -> None:
        target_versions = ctx.target_versions

        if 49 in target_versions:
            for item in self._js_imports:
                if (
                    item.module == "resource:///org/gnome/shell/ui/calendar.js"
                    and "DoNotDisturbSwitch" in item.snippet
                ):
                    ctx.add_finding(
                        R.EGO_C49_001,
                        (
                            "This extension explicitly targets GNOME Shell "
                            "49 but still imports `DoNotDisturbSwitch` from "
                            "`calendar.js`."
                        ),
                        [ctx.import_evidence(item)],
                    )

            _append_removed_api_findings(
                ctx,
                text,
                root,
                [
                    (
                        R.EGO_C49_002,
                        (
                            "This extension explicitly targets GNOME Shell 49 "
                            "but still uses removed `Clutter.ClickAction` or "
                            "`Clutter.TapAction`."
                        ),
                        _is_removed_clutter_action,
                    ),
                    (
                        R.EGO_C49_003,
                        (
                            "This extension explicitly targets GNOME Shell 49 "
                            "but still passes `Meta.MaximizeFlags` to "
                            "`maximize()` or `unmaximize()`."
                        ),
                        _uses_removed_maximize_flags,
                    ),
                    (
                        R.EGO_C49_004,
                        (
                            "This extension explicitly targets GNOME Shell 49 "
                            "but still calls removed "
                            "`Meta.Window.get_maximized()`."
                        ),
                        lambda source, node: _calls_removed_method(
                            source, node, {"get_maximized"}
                        ),
                    ),
                    (
                        R.EGO_C49_005,
                        (
                            "This extension explicitly targets GNOME Shell 49 "
                            "but still calls removed "
                            "`Meta.CursorTracker.set_pointer_visible()`."
                        ),
                        lambda source, node: _calls_removed_method(
                            source, node, {"set_pointer_visible"}
                        ),
                    ),
                ],
            )

        if 50 not in target_versions:
            return

        imports_run_dialog = any(
            item.module == "resource:///org/gnome/shell/ui/runDialog.js"
            for item in self._js_imports
        )
        _append_removed_api_findings(
            ctx,
            text,
            root,
            [
                (
                    R.EGO_C50_001,
                    (
                        "This extension explicitly targets GNOME Shell 50 but "
                        "still relies on removed `global.display` "
                        "restart-related signals."
                    ),
                    lambda source, node: _connects_removed_display_signal(
                        source, node
                    ),
                ),
                (
                    R.EGO_C50_002,
                    (
                        "This extension explicitly targets GNOME Shell 50 but "
                        "still calls `RunDialog._restart()`."
                    ),
                    lambda source, node: (
                        imports_run_dialog
                        and _calls_removed_method(source, node, {"_restart"})
                    ),
                ),
            ],
        )
