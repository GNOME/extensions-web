# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from ...spec import R
from .api import JSFileCheckContext, JSFileFacts, JSFileRule

_LOG_METHODS = frozenset({"log", "warn", "error"})
_DEBUG_NAMES = frozenset({"debug", "_debug", "verbose", "_verbose"})

# Maximum number of ungated console calls allowed per file.
_THRESHOLD = 5


class ExcessiveLoggingRule(JSFileRule):
    """JSFileRule: EGO_A_004 — excessive ungated console.log/warn/error calls."""

    def check(self, facts: JSFileFacts, ctx: JSFileCheckContext) -> None:
        evidences = []
        for method in _LOG_METHODS:
            for site in facts.model.calls.find("console", method):
                if not any(
                    name.lower() in _DEBUG_NAMES for name in site.guard_identifiers
                ):
                    evidences.append(ctx.node_evidence(facts.model.text, site.node))

        if len(evidences) > _THRESHOLD:
            ctx.add_finding(
                R.EGO_A_004,
                (
                    f"File contains {len(evidences)} ungated "
                    f"console.log/warn/error calls (threshold: {_THRESHOLD})."
                ),
                evidences[:10],
            )
