# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from tree_sitter import Node

from ...api_data import API
from ...ast import member_expression_parts, node_text
from ...spec import R
from ..context import CheckContext
from ..engine import FileRule, NodeRule

DEPRECATED_IMPORT_TOKENS = API.imports.deprecated_modules
SHELL_FORBIDDEN_TOKENS = API.imports.shell_forbidden_libs
PREFS_FORBIDDEN_TOKENS = API.imports.prefs_forbidden_libs



class DeprecatedImportsRule(FileRule):
    """FileRule: EGO_I_001 — deprecated module imports (ByteArray, Lang, Mainloop)."""

    def __init__(self, js_imports: list) -> None:
        self._js_imports = js_imports

    def check(self, root: Node, text: str, ctx: CheckContext) -> None:
        for token in DEPRECATED_IMPORT_TOKENS:
            evidences = []

            for item in self._js_imports:
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


class ImportsGiRule(NodeRule):
    """NodeRule: EGO_I_004 — direct use of imports._gi."""

    node_types: frozenset[str] = frozenset({"member_expression"})

    def __init__(self) -> None:
        self._evidences: list = []
        self._seen_lines: set[int] = set()

    def visit(self, node: Node, text: str, ctx: CheckContext) -> None:
        parts = member_expression_parts(text, node)
        if len(parts) >= 2 and parts[0] == "imports" and parts[1] == "_gi":
            line = node.start_point.row + 1
            if line not in self._seen_lines:
                self._seen_lines.add(line)
                self._evidences.append(
                    ctx.display_evidence(
                        line=line,
                        snippet=node_text(text, node)[:300],
                    )
                )

    def finalize(self, root: Node, text: str, ctx: CheckContext) -> None:
        if self._evidences:
            ctx.add_finding(
                R.EGO_I_004,
                "Direct use of `imports._gi` is discouraged in extensions.",
                self._evidences,
            )


class ForbiddenLibsRule(FileRule):
    """FileRule: EGO_I_002/EGO_I_003 — GTK libs in shell, Shell libs in prefs."""

    def __init__(self, js_imports: list) -> None:
        self._js_imports = js_imports

    def check(self, root: Node, text: str, ctx: CheckContext) -> None:
        if "shell" in ctx.file_contexts:
            self._check_forbidden(
                R.EGO_I_002,
                ctx,
                SHELL_FORBIDDEN_TOKENS,
                "GTK library `{token}` must not be imported in shell process files.",
            )
        if "prefs" in ctx.file_contexts:
            self._check_forbidden(
                R.EGO_I_003,
                ctx,
                PREFS_FORBIDDEN_TOKENS,
                "GNOME Shell library `{token}` must not be imported "
                "in preferences files.",
            )

    def _check_forbidden(
        self,
        rule_id: str,
        ctx: CheckContext,
        forbidden_tokens: frozenset[str],
        message_template: str,
    ) -> None:
        for item in self._js_imports:
            token = None
            if item.module and item.module.startswith("gi://"):
                token = item.module.removeprefix("gi://").split("?")[0]

            if token in forbidden_tokens:
                ctx.add_finding(
                    rule_id,
                    message_template.format(token=token),
                    [ctx.import_evidence(item)],
                )
