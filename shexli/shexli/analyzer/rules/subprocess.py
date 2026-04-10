# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from ...spec import R

if TYPE_CHECKING:
    from shexli.models import Evidence
from ..engine import JSContext
from ..facts.file import (
    SpawnWrapperFact,
)
from .api import JSFileCheckContext, JSFileFacts, JSFileRule
from .constants import (
    NON_PKEXEC_PRIVILEGE_COMMANDS,
    SHELL_SYNC_SPAWN_CALL_NAMES,
    SPAWN_CALL_NAMES,
)

_PRIVILEGED_WRAPPER_CALL_NAMES = frozenset({"runProcess"})


class SubprocessRule(JSFileRule):
    """JSFileRule: EGO_X_001/EGO_X_002 — privileged and synchronous subprocess calls."""

    required_file_facts = (SpawnWrapperFact,)

    def check(self, facts: JSFileFacts, ctx: JSFileCheckContext) -> None:
        text = facts.model.text
        spawn_wrapper_fact = facts.get_fact(SpawnWrapperFact)

        privileged_evidences: list[Evidence] = []
        sync_evidences: list[Evidence] = []

        # Synchronous spawn in shell context
        if JSContext.EXTENSION in ctx.contexts:
            for call_str in SHELL_SYNC_SPAWN_CALL_NAMES:
                parts = tuple(call_str.split("."))
                for site in facts.model.calls.find(*parts):
                    sync_evidences.append(ctx.node_evidence(text, site.node))

        # Standard spawn calls — check for privileged commands in argv
        for call_str in SPAWN_CALL_NAMES:
            parts = tuple(call_str.split("."))
            for site in facts.model.calls.find(*parts):
                command_head = site.literal_argv[0] if site.literal_argv else None
                if command_head in NON_PKEXEC_PRIVILEGE_COMMANDS:
                    privileged_evidences.append(ctx.node_evidence(text, site.node))

        # GLib.shell_parse_argv — splits a command string into argv
        for site in facts.model.calls.find("GLib", "shell_parse_argv"):
            command_head = site.first_arg_argv_head
            if command_head in NON_PKEXEC_PRIVILEGE_COMMANDS:
                privileged_evidences.append(ctx.node_evidence(text, site.node))

        # Privileged wrapper calls (e.g. runProcess)
        for name in _PRIVILEGED_WRAPPER_CALL_NAMES:
            for site in facts.model.calls.find(name):
                command_head = site.first_arg_argv_head
                if command_head in NON_PKEXEC_PRIVILEGE_COMMANDS:
                    privileged_evidences.append(ctx.node_evidence(text, site.node))

        # User-defined wrapper functions detected by SpawnWrapperCollector
        for name in spawn_wrapper_fact.wrappers:
            for site in facts.model.calls.find(name):
                command_head = site.first_arg_argv_head
                if command_head in NON_PKEXEC_PRIVILEGE_COMMANDS:
                    privileged_evidences.append(ctx.node_evidence(text, site.node))

        if privileged_evidences:
            ctx.add_finding(
                R.EGO_X_001,
                (
                    "Privileged subprocess patterns must use `pkexec`, not "
                    "`sudo`, `su`, `doas`, or similar wrappers."
                ),
                privileged_evidences,
            )

        if sync_evidences:
            ctx.add_finding(
                R.EGO_X_002,
                (
                    "Shell code should avoid synchronous subprocess APIs like "
                    "`GLib.spawn_command_line_sync()` and `GLib.spawn_sync()`."
                ),
                sync_evidences,
            )
