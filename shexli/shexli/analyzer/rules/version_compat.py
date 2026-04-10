# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from ...spec import R

if TYPE_CHECKING:
    from shexli.models import Evidence
from .api import (
    JSFileCheckContext,
    JSFileFacts,
    JSFileRule,
)
from .constants import (
    GNOME49_SIGNAL_REMOVED_CLASSES,
    GNOME50_REMOVED_DISPLAY_SIGNALS,
)

# Pre-computed tuple keys for new_expressions lookups
_GNOME49_REMOVED_CTORS: frozenset[tuple[str, ...]] = frozenset(
    tuple(name.split(".")) for name in GNOME49_SIGNAL_REMOVED_CLASSES
)


class Gnome49CompatRule(JSFileRule):
    """JSFileRule: EGO_C49 — removed APIs in GNOME Shell 49."""

    applies_to_versions: frozenset[int] | None = frozenset({49})

    def check(self, facts: JSFileFacts, ctx: JSFileCheckContext) -> None:
        text = facts.model.text

        clutter_evidences: list[Evidence] = []
        maximize_evidences: list[Evidence] = []
        get_maximized_evidences: list[Evidence] = []
        pointer_evidences: list[Evidence] = []

        # Removed Clutter action classes
        for ctor_parts in _GNOME49_REMOVED_CTORS:
            for site in facts.model.new_expressions.find(*ctor_parts):
                clutter_evidences.append(ctx.node_evidence(text, site.node))

        # maximize/unmaximize with Meta.MaximizeFlags argument
        for suffix in [("maximize",), ("unmaximize",)]:
            for site in facts.model.calls.find_suffix(*suffix):
                if any(
                    parts is not None and parts[:2] == ("Meta", "MaximizeFlags")
                    for parts in site.arg_member_parts
                ):
                    maximize_evidences.append(ctx.node_evidence(text, site.node))

        # Removed Meta.Window.get_maximized()
        for site in facts.model.calls.find_suffix("get_maximized"):
            get_maximized_evidences.append(ctx.node_evidence(text, site.node))

        # Removed Meta.CursorTracker.set_pointer_visible()
        for site in facts.model.calls.find_suffix("set_pointer_visible"):
            pointer_evidences.append(ctx.node_evidence(text, site.node))

        # Removed DoNotDisturbSwitch import
        for item in facts.model.imports:
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

        if clutter_evidences:
            ctx.add_finding(
                R.EGO_C49_002,
                (
                    "This extension explicitly targets GNOME Shell 49 "
                    "but still uses removed `Clutter.ClickAction` or "
                    "`Clutter.TapAction`."
                ),
                clutter_evidences,
            )

        if maximize_evidences:
            ctx.add_finding(
                R.EGO_C49_003,
                (
                    "This extension explicitly targets GNOME Shell 49 "
                    "but still passes `Meta.MaximizeFlags` to "
                    "`maximize()` or `unmaximize()`."
                ),
                maximize_evidences,
            )

        if get_maximized_evidences:
            ctx.add_finding(
                R.EGO_C49_004,
                (
                    "This extension explicitly targets GNOME Shell 49 "
                    "but still calls removed "
                    "`Meta.Window.get_maximized()`."
                ),
                get_maximized_evidences,
            )

        if pointer_evidences:
            ctx.add_finding(
                R.EGO_C49_005,
                (
                    "This extension explicitly targets GNOME Shell 49 "
                    "but still calls removed "
                    "`Meta.CursorTracker.set_pointer_visible()`."
                ),
                pointer_evidences,
            )


class Gnome50CompatRule(JSFileRule):
    """JSFileRule: EGO_C50 — removed APIs in GNOME Shell 50."""

    applies_to_versions: frozenset[int] | None = frozenset({50})

    def check(self, facts: JSFileFacts, ctx: JSFileCheckContext) -> None:
        text = facts.model.text

        display_signal_evidences: list[Evidence] = []
        restart_evidences: list[Evidence] = []
        imports_run_dialog = any(
            item.module == "resource:///org/gnome/shell/ui/runDialog.js"
            for item in facts.model.imports
        )

        # Removed global.display restart-related signals
        for site in facts.model.calls.find("global", "display", "connect"):
            if not site.arg_literals:
                continue
            signal = site.arg_literals[0]
            if signal in GNOME50_REMOVED_DISPLAY_SIGNALS:
                display_signal_evidences.append(ctx.node_evidence(text, site.node))

        # Removed RunDialog._restart()
        if imports_run_dialog:
            for site in facts.model.calls.find_suffix("_restart"):
                restart_evidences.append(ctx.node_evidence(text, site.node))

        if display_signal_evidences:
            ctx.add_finding(
                R.EGO_C50_001,
                (
                    "This extension explicitly targets GNOME Shell 50 but "
                    "still relies on removed `global.display` "
                    "restart-related signals."
                ),
                display_signal_evidences,
            )

        if restart_evidences:
            ctx.add_finding(
                R.EGO_C50_002,
                (
                    "This extension explicitly targets GNOME Shell 50 but "
                    "still calls `RunDialog._restart()`."
                ),
                restart_evidences,
            )
