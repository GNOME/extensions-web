# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from tree_sitter import Node

from ...ast import iter_nodes, member_expression_parts, node_text
from ...spec import R
from ..context import CheckContext
from ..engine import FileRule

DEPRECATED_IMPORT_TOKENS = ("ByteArray", "Lang", "Mainloop")
SHELL_FORBIDDEN_TOKENS = frozenset({"Gtk", "Gdk", "Adw"})
PREFS_FORBIDDEN_TOKENS = frozenset({"Clutter", "Meta", "St", "Shell"})



class DeprecatedImportsRule(FileRule):
    """FileRule: EGO017 — deprecated module imports (ByteArray, Lang, Mainloop)."""

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
                    R.EGO017,
                    f"Deprecated module `{token}` is imported.",
                    evidences,
                )


class ImportsGiRule:
    """FileRule: EGO031 — direct use of imports._gi."""

    def check(self, root: Node, text: str, ctx: CheckContext) -> None:
        evidences = []
        seen_lines: set[int] = set()

        for node in iter_nodes(root):
            if node.type != "member_expression":
                continue
            parts = member_expression_parts(text, node)
            if len(parts) >= 2 and parts[0] == "imports" and parts[1] == "_gi":
                line = node.start_point.row + 1
                if line not in seen_lines:
                    seen_lines.add(line)
                    evidences.append(
                        ctx.display_evidence(
                            line=line,
                            snippet=node_text(text, node)[:300],
                        )
                    )

        if evidences:
            ctx.add_finding(
                R.EGO031,
                "Direct use of `imports._gi` is discouraged in extensions.",
                evidences,
            )


class ForbiddenLibsRule(FileRule):
    """FileRule: EGO018/EGO019 — GTK libs in shell, Shell libs in prefs."""

    def __init__(self, js_imports: list) -> None:
        self._js_imports = js_imports

    def check(self, root: Node, text: str, ctx: CheckContext) -> None:
        if "shell" in ctx.file_contexts:
            self._check_forbidden(
                R.EGO018,
                ctx,
                SHELL_FORBIDDEN_TOKENS,
                "GTK library `{token}` must not be imported in shell process files.",
            )
        if "prefs" in ctx.file_contexts:
            self._check_forbidden(
                R.EGO019,
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
