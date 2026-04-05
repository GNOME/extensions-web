# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from tree_sitter import Node

from ...ast import (
    default_export_class_methods,
    legacy_entrypoint_methods,
    node_text,
)
from ...spec import R
from ..context import CheckContext
from ..engine import FileRule
from ..lifecycle import method_reachability


class SessionModesRule(FileRule):
    """FileRule: EGO008 — unlock-dialog must be documented in disable()."""

    def __init__(self, metadata: dict | None) -> None:
        self._metadata = metadata

    def check(self, root: Node, text: str, ctx: CheckContext) -> None:
        if (
            ctx.path.name != "extension.js"
            or "shell" not in ctx.file_contexts
            or not self._metadata
            or not self._metadata.get("session-modes")
            or "unlock-dialog" not in self._metadata["session-modes"]
        ):
            return

        methods = default_export_class_methods(text, root) or legacy_entrypoint_methods(
            text, root
        )
        disable_methods = method_reachability(text, methods, ["disable"])

        disable_texts = [
            node_text(text, body)
            for method in disable_methods
            if (body := method.child_by_field_name("body")) is not None
        ]
        comment_near_disable = any(
            "//" in block[:400] or "/*" in block[:400] for block in disable_texts
        )

        if not comment_near_disable:
            ctx.add_finding(
                R.EGO008,
                (
                    "Extensions using `unlock-dialog` should document "
                    "the reason in `disable()` comments."
                ),
                [
                    ctx.display_evidence(
                        snippet=(
                            "unlock-dialog declared but no nearby "
                            "disable() comment found"
                        )
                    )
                ],
            )
