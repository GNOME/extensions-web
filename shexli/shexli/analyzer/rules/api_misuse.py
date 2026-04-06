# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from tree_sitter import Node

from ...api_data import API
from ...ast import (
    call_arguments,
    call_callee_parts,
    identifier_name,
    iter_nodes,
)
from ...models import Evidence
from ...spec import R
from ..context import CheckContext
from ..engine import FileRule
from ..spawn import extract_literal_string

_SHELL_SYNC_FILE_IO_CALL_NAMES = API.subprocess.sync_file_io_calls
_EXTENSION_LOOKUP_CALL_NAMES = API.api_misuse.extension_lookup_calls

class ApiMisuseRule(FileRule):
    """FileRule: EGO_X_003/EGO_X_004/EGO_X_005/EGO_X_006 — run_dispose, sync IO,
    stylesheet misuse, and extension lookup."""

    def check(self, root: Node, text: str, ctx: CheckContext) -> None:
        run_dispose_evidences: list[Evidence] = []
        sync_io_evidences: list[Evidence] = []
        stylesheet_evidences: list[Evidence] = []
        extension_lookup_evidences: list[Evidence] = []
        stylesheet_aliases: set[str] = set()

        for node in iter_nodes(root):
            if node.type == "variable_declarator":
                name = node.child_by_field_name("name")
                value = node.child_by_field_name("value")
                if name is None or value is None or value.type != "call_expression":
                    continue

                call_name = ".".join(call_callee_parts(text, value))
                args = call_arguments(value)
                if (
                    call_name.endswith(".get_child")
                    and args
                    and extract_literal_string(text, args[0]) == "stylesheet.css"
                ):
                    alias = identifier_name(text, name)
                    if alias:
                        stylesheet_aliases.add(alias)
                continue

            if node.type != "call_expression":
                continue

            call_name = ".".join(call_callee_parts(text, node))
            if "shell" in ctx.file_contexts and (
                call_name in _SHELL_SYNC_FILE_IO_CALL_NAMES
                or call_name.endswith(".load_contents")
                or call_name.endswith(".load_bytes")
            ):
                sync_io_evidences.append(ctx.node_evidence(text, node))

            if call_name.endswith(".run_dispose") or call_name == "run_dispose":
                run_dispose_evidences.append(ctx.node_evidence(text, node))

            if call_name in _EXTENSION_LOOKUP_CALL_NAMES:
                extension_lookup_evidences.append(ctx.node_evidence(text, node))

            if "shell" not in ctx.file_contexts or not call_name.endswith(
                (".load_stylesheet", ".unload_stylesheet")
            ):
                continue

            args = call_arguments(node)
            if not args:
                continue

            if args[0].text is None:
                continue

            arg_text = args[0].text.decode("utf-8")
            literal = extract_literal_string(text, args[0])
            if literal == "stylesheet.css" or arg_text in stylesheet_aliases:
                stylesheet_evidences.append(ctx.node_evidence(text, node))

        if run_dispose_evidences:
            ctx.add_finding(
                R.EGO_X_003,
                "Extension code should not call `run_dispose()`.",
                run_dispose_evidences,
            )

        if sync_io_evidences:
            ctx.add_finding(
                R.EGO_X_004,
                (
                    "Shell code should avoid synchronous file IO APIs like "
                    "`GLib.file_get_contents()` and `Gio.File.load_contents()`."
                ),
                sync_io_evidences,
            )

        if stylesheet_evidences:
            ctx.add_finding(
                R.EGO_X_005,
                (
                    "Extensions should not manually load or unload the default "
                    "`stylesheet.css`; GNOME Shell handles it automatically."
                ),
                stylesheet_evidences,
            )

        if extension_lookup_evidences:
            ctx.add_finding(
                R.EGO_X_006,
                (
                    "Use `this`, `this.getSettings()` or `this.path` instead of "
                    "`lookupByURL()` or `lookupByUUID()` for the current "
                    "extension."
                ),
                extension_lookup_evidences,
            )
