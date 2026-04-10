# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from ...spec import R
from ..facts.file import FileShapeFact
from .api import JSFileCheckContext, JSFileFacts, JSFileRule

# Files smaller than this are not checked to avoid false positives on stubs.
_MIN_FILE_BYTES = 500

# Fraction of non-conventional short (1–2 char) identifiers above which
# the file is considered name-mangled.
_SHORT_IDENT_RATIO = 0.55

# Minimum number of identifiers required to apply the ratio check.
_MIN_IDENT_COUNT = 25

# A file this large with so few lines is almost certainly minified.
_MINIFIED_LINE_BYTES = 500
_MINIFIED_MAX_LINES = 4


class ObfuscationRule(JSFileRule):
    """JSFileRule: EGO_A_001 — minification / obfuscation heuristic."""

    required_file_facts = (FileShapeFact,)

    def check(self, facts: JSFileFacts, ctx: JSFileCheckContext) -> None:
        file_shape = facts.get_fact(FileShapeFact)
        if file_shape.file_size_bytes < _MIN_FILE_BYTES:
            return

        _check_name_mangling(file_shape, ctx)
        _check_minified_layout(file_shape, ctx)


def _check_name_mangling(file_shape: FileShapeFact, ctx: JSFileCheckContext) -> None:
    if file_shape.scored_identifier_count < _MIN_IDENT_COUNT:
        return

    ratio = file_shape.short_identifier_ratio
    avg_len = file_shape.avg_identifier_length
    if ratio is None or avg_len is None:
        return

    if ratio < _SHORT_IDENT_RATIO:
        return

    ctx.add_finding(
        R.EGO_A_001,
        (
            f"File appears obfuscated: {ratio:.0%} of identifiers are "
            f"1–2 characters (avg length {avg_len:.1f})."
        ),
        [
            ctx.display_evidence(
                snippet=(
                    f"short identifier ratio: {ratio:.0%}, "
                    f"identifiers scored: {file_shape.scored_identifier_count}"
                )
            )
        ],
    )


def _check_minified_layout(file_shape: FileShapeFact, ctx: JSFileCheckContext) -> None:
    if file_shape.non_empty_line_count > _MINIFIED_MAX_LINES:
        return

    file_bytes = file_shape.file_size_bytes
    if file_bytes < _MINIFIED_LINE_BYTES * _MINIFIED_MAX_LINES:
        return

    ctx.add_finding(
        R.EGO_A_001,
        (
            f"File appears minified: {file_bytes} bytes "
            f"compressed into {file_shape.non_empty_line_count} line(s)."
        ),
        [
            ctx.display_evidence(
                snippet=(
                    "file size: "
                    f"{file_bytes} bytes, non-empty lines: "
                    f"{file_shape.non_empty_line_count}"
                )
            )
        ],
    )
