# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from tree_sitter import Node

from ...ast import call_callee_parts, iter_nodes
from ...spec import R
from ..context import CheckContext
from ..engine import FileRule

_LOG_METHODS = frozenset({"log", "warn", "error"})
_DEBUG_NAMES = frozenset({"debug", "_debug", "DEBUG", "verbose", "_verbose", "VERBOSE"})

# Maximum number of ungated console calls allowed per file.
_THRESHOLD = 5


def _is_inside_debug_guard(node: Node) -> bool:
    """Return True if *node* is nested inside the *consequent* branch of an
    if-statement whose condition looks like a debug flag (identifier or
    member-expression whose last part is a known debug name).

    The else branch is intentionally excluded: production logging under
    ``else`` should still be counted as ungated."""
    prev = node
    current = node.parent
    while current is not None:
        if current.type == "if_statement":
            cond = current.child_by_field_name("condition")
            if cond is not None and _condition_is_debug(cond):
                if current.child_by_field_name("consequence") is prev:
                    return True
        prev = current
        current = current.parent
    return False


def _condition_is_debug(node: Node) -> bool:
    t = node.type
    if t == "identifier":
        return node.text is not None and node.text.decode() in _DEBUG_NAMES
    if t == "member_expression":
        prop = node.child_by_field_name("property")
        if prop is not None and prop.text is not None:
            return prop.text.decode() in _DEBUG_NAMES
    # Handles `!debug` etc.
    if t in {"unary_expression", "parenthesized_expression"}:
        for child in node.children:
            if _condition_is_debug(child):
                return True
    return False

class ExcessiveLoggingRule(FileRule):
    """FileRule: EGO_A_004 — excessive ungated console.log/warn/error calls."""

    def check(self, root: Node, text: str, ctx: CheckContext) -> None:
        evidences = []

        for node in iter_nodes(root):
            if node.type != "call_expression":
                continue

            parts = call_callee_parts(text, node)
            if len(parts) != 2 or parts[0] != "console":
                continue

            if parts[1] not in _LOG_METHODS:
                continue

            if _is_inside_debug_guard(node):
                continue

            evidences.append(ctx.node_evidence(text, node))

        if len(evidences) > _THRESHOLD:
            ctx.add_finding(
                R.EGO_A_004,
                (
                    f"File contains {len(evidences)} ungated "
                    f"console.log/warn/error calls (threshold: {_THRESHOLD})."
                ),
                evidences[:10],
            )
