# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from tree_sitter import Node

from ...ast import iter_nodes
from ...spec import R
from ..context import CheckContext
from ..engine import FileRule

# Files smaller than this are not checked to avoid false positives on stubs.
_MIN_FILE_BYTES = 500

# Single-character identifiers that are legitimate in normal JS code.
# Includes gettext alias (_), loop variables, common short names.
_CONVENTIONAL_SINGLE = frozenset({
    "_", "i", "j", "k", "n", "x", "y", "e", "t", "s", "v", "r", "p",
})

# Fraction of non-conventional short (1–2 char) identifiers above which
# the file is considered name-mangled.
_SHORT_IDENT_RATIO = 0.55

# Minimum number of identifiers required to apply the ratio check.
_MIN_IDENT_COUNT = 25

# A file this large with so few lines is almost certainly minified.
_MINIFIED_LINE_BYTES = 500
_MINIFIED_MAX_LINES = 4


class ObfuscationRule(FileRule):
    """FileRule: EGO020 — minification / obfuscation heuristic."""

    def check(self, root: Node, text: str, ctx: CheckContext) -> None:
        if len(text.encode()) < _MIN_FILE_BYTES:
            return

        self._check_name_mangling(root, ctx)
        self._check_minified_layout(text, ctx)

    def _check_name_mangling(self, root: Node, ctx: CheckContext) -> None:
        idents = [
            node.text.decode()
            for node in iter_nodes(root)
            if node.type == "identifier" and node.text is not None
        ]
        if len(idents) < _MIN_IDENT_COUNT:
            return

        # Exclude conventional single-char names before scoring.
        scored = [i for i in idents if i not in _CONVENTIONAL_SINGLE]
        if not scored:
            return

        short = sum(1 for i in scored if len(i) <= 2)
        ratio = short / len(scored)
        if ratio < _SHORT_IDENT_RATIO:
            return

        avg_len = sum(len(i) for i in scored) / len(scored)
        ctx.add_finding(
            R.EGO020,
            (
                f"File appears obfuscated: {ratio:.0%} of identifiers are "
                f"1–2 characters (avg length {avg_len:.1f})."
            ),
            [
                ctx.display_evidence(
                    snippet=(
                        f"short identifier ratio: {ratio:.0%}, "
                        f"identifiers scored: {len(scored)}"
                    )
                )
            ],
        )

    def _check_minified_layout(self, text: str, ctx: CheckContext) -> None:
        lines = text.splitlines()
        non_empty = [l for l in lines if l.strip()]
        if len(non_empty) > _MINIFIED_MAX_LINES:
            return

        file_bytes = len(text.encode())
        if file_bytes < _MINIFIED_LINE_BYTES * _MINIFIED_MAX_LINES:
            return

        ctx.add_finding(
            R.EGO020,
            (
                f"File appears minified: {file_bytes} bytes "
                f"compressed into {len(non_empty)} line(s)."
            ),
            [
                ctx.display_evidence(
                    snippet=(
                        f"file size: {file_bytes} bytes, "
                        f"non-empty lines: {len(non_empty)}"
                    )
                )
            ],
        )
