# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from ...spec import R
from .api import JSFileCheckContext, JSFileFacts, JSFileRule


class ClipboardRule(JSFileRule):
    """JSFileRule: EGO_A_005 — St.Clipboard.get_default() direct access."""

    def check(self, facts: JSFileFacts, ctx: JSFileCheckContext) -> None:
        sites = facts.model.calls.find("St", "Clipboard", "get_default")
        if sites:
            ctx.add_finding(
                R.EGO_A_005,
                "Direct clipboard access via `St.Clipboard.get_default()` "
                "requires reviewer scrutiny.",
                [ctx.node_evidence(facts.model.text, s.node) for s in sites],
            )
