# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from ...spec import R
from ..engine import JSContext
from ..facts.file import StylesheetBindingFact
from .api import JSFileCheckContext, JSFileFacts, JSFileRule
from .constants import (
    EXTENSION_LOOKUP_CALL_NAMES,
    SYNC_FILE_IO_CALL_NAMES,
)


class ApiMisuseRule(JSFileRule):
    """JSFileRule: EGO_X_003/EGO_X_004/EGO_X_005/EGO_X_006 — run_dispose, sync IO,
    stylesheet misuse, and extension lookup."""

    required_file_facts = (StylesheetBindingFact,)

    def check(self, facts: JSFileFacts, ctx: JSFileCheckContext) -> None:
        text = facts.model.text
        stylesheet_binding_fact = facts.get_fact(StylesheetBindingFact)

        run_dispose_evidences = []
        sync_io_evidences = []
        stylesheet_evidences = []
        extension_lookup_evidences = []

        # run_dispose
        for site in facts.model.calls.find_suffix("run_dispose"):
            run_dispose_evidences.append(ctx.node_evidence(text, site.node))

        # extension lookup
        for call_str in EXTENSION_LOOKUP_CALL_NAMES:
            parts = tuple(call_str.split("."))
            for site in facts.model.calls.find(*parts):
                extension_lookup_evidences.append(ctx.node_evidence(text, site.node))

        if JSContext.EXTENSION in ctx.contexts:
            # Synchronous file IO
            seen: set[int] = set()
            for call_str in SYNC_FILE_IO_CALL_NAMES:
                parts = tuple(call_str.split("."))
                for site in facts.model.calls.find(*parts):
                    if id(site.node) not in seen:
                        seen.add(id(site.node))
                        sync_io_evidences.append(ctx.node_evidence(text, site.node))
            for suffix in [("load_contents",), ("load_bytes",)]:
                for site in facts.model.calls.find_suffix(*suffix):
                    if id(site.node) not in seen:
                        seen.add(id(site.node))
                        sync_io_evidences.append(ctx.node_evidence(text, site.node))

            # Stylesheet misuse
            for suffix in [("load_stylesheet",), ("unload_stylesheet",)]:
                for site in facts.model.calls.find_suffix(*suffix):
                    if not site.arg_literals:
                        continue
                    if (
                        site.arg_literals[0] == "stylesheet.css"
                        or site.arg_identifiers[0] in stylesheet_binding_fact.bindings
                    ):
                        stylesheet_evidences.append(ctx.node_evidence(text, site.node))

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
