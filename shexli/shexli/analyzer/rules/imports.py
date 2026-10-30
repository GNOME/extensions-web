# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from ...spec import R
from ..engine import JSContext
from .api import JSFileCheckContext, JSFileFacts, JSFileRule
from .constants import (
    DEPRECATED_IMPORT_TOKENS,
    PREFS_FORBIDDEN_TOKENS,
    SHELL_FORBIDDEN_TOKENS,
)


class DeprecatedImportsRule(JSFileRule):
    """JSFileRule: EGO_I_001 — deprecated module imports (ByteArray, Lang, Mainloop)."""

    def check(self, facts: JSFileFacts, ctx: JSFileCheckContext) -> None:
        for token in DEPRECATED_IMPORT_TOKENS:
            evidences = []

            for item in facts.model.imports:
                if item.module in {
                    f"gi://{token}",
                    f"imports.{token.lower()}",
                } or any(token in name for name in item.names):
                    evidences.append(ctx.import_evidence(item))

            if evidences:
                ctx.add_finding(
                    R.EGO_I_001,
                    f"Deprecated module `{token}` is imported.",
                    evidences,
                )


class ImportsGiRule(JSFileRule):
    """JSFileRule: EGO_I_004 — direct use of imports._gi."""

    def check(self, facts: JSFileFacts, ctx: JSFileCheckContext) -> None:
        sites = facts.model.member_expressions.find_prefix("imports", "_gi")
        if sites:
            seen_lines: set[int] = set()
            evidences = []
            for site in sites:
                line = site.node.start_point.row + 1
                if line in seen_lines:
                    continue
                seen_lines.add(line)
                evidences.append(ctx.node_evidence(facts.model.text, site.node))
            ctx.add_finding(
                R.EGO_I_004,
                "Direct use of `imports._gi` is discouraged in extensions.",
                evidences,
            )


class ForbiddenLibsRule(JSFileRule):
    """JSFileRule: EGO_I_002/EGO_I_003 — GTK libs in extension, Shell libs in prefs."""

    def check(self, facts: JSFileFacts, ctx: JSFileCheckContext) -> None:
        if JSContext.EXTENSION in ctx.contexts:
            self._check_forbidden(
                R.EGO_I_002,
                facts,
                ctx,
                SHELL_FORBIDDEN_TOKENS,
                (
                    "GTK library `{token}` must not be imported in "
                    "extension process files."
                ),
            )
        if JSContext.PREFERENCES in ctx.contexts:
            self._check_forbidden(
                R.EGO_I_003,
                facts,
                ctx,
                PREFS_FORBIDDEN_TOKENS,
                (
                    "GNOME Shell library `{token}` must not be imported in "
                    "preferences files."
                ),
            )

    def _check_forbidden(
        self,
        rule_id: str,
        facts: JSFileFacts,
        ctx: JSFileCheckContext,
        forbidden_tokens: frozenset[str],
        message_template: str,
    ) -> None:
        for item in facts.model.imports:
            token = None
            if item.module and item.module.startswith("gi://"):
                token = item.module.removeprefix("gi://").split("?")[0]

            if token in forbidden_tokens:
                ctx.add_finding(
                    rule_id,
                    message_template.format(token=token),
                    [ctx.import_evidence(item)],
                )
