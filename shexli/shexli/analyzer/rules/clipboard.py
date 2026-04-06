# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from tree_sitter import Node

from ...ast import call_callee_parts
from ...spec import R
from ..context import CheckContext
from ..engine import NodeRule


class ClipboardRule(NodeRule):
    """NodeRule: EGO_A_005 — direct clipboard access via St.Clipboard.get_default()."""

    node_types: frozenset[str] = frozenset({"call_expression"})

    def __init__(self) -> None:
        self._evidences: list = []

    def visit(self, node: Node, text: str, ctx: CheckContext) -> None:
        if call_callee_parts(text, node) == ["St", "Clipboard", "get_default"]:
            self._evidences.append(ctx.node_evidence(text, node))

    def finalize(self, root: Node, text: str, ctx: CheckContext) -> None:
        if self._evidences:
            ctx.add_finding(
                R.EGO_A_005,
                "Direct clipboard access via `St.Clipboard.get_default()` "
                "requires reviewer scrutiny.",
                self._evidences,
            )
