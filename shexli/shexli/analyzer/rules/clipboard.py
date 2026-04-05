# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from tree_sitter import Node

from ...ast import call_callee_parts, iter_nodes
from ...spec import R
from ..context import CheckContext


class ClipboardRule:
    """FileRule: EGO039 — direct clipboard access via St.Clipboard.get_default()."""

    def check(self, root: Node, text: str, ctx: CheckContext) -> None:
        evidences = []

        for node in iter_nodes(root):
            if node.type != "call_expression":
                continue

            parts = call_callee_parts(text, node)
            if parts == ["St", "Clipboard", "get_default"]:
                evidences.append(ctx.node_evidence(text, node))

        if evidences:
            ctx.add_finding(
                R.EGO039,
                "Direct clipboard access via `St.Clipboard.get_default()` "
                "requires reviewer scrutiny.",
                evidences,
            )
