# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from tree_sitter import Node

from ...api_data import API
from ...ast import (
    call_arguments,
    call_callee_parts,
    identifier_name,
    iter_nodes,
    top_level_function_methods,
)
from ...models import Evidence
from ...spec import R
from ..context import CheckContext
from ..engine import FileRule
from ..spawn import (
    SPAWN_CALL_NAMES,
    extract_literal_argv,
    extract_literal_argv_head,
    extract_literal_string,
    extract_spawn_argv,
)

_NON_PKEXEC_PRIVILEGE_COMMANDS = API.subprocess.privilege_commands
_PRIVILEGED_WRAPPER_CALL_NAMES = {"runProcess"}
_SHELL_SYNC_SPAWN_CALL_NAMES = API.subprocess.sync_spawn_calls


def _argv_spawn_wrapper_functions(text: str, root: Node) -> set[str]:
    wrappers: set[str] = set()

    for name, methods in top_level_function_methods(text, root).items():
        for method in methods:
            params = method.child_by_field_name("parameters")
            body = method.child_by_field_name("body")
            if params is None or body is None or not params.named_children:
                continue

            argv_param = identifier_name(text, params.named_children[0])
            if not argv_param:
                continue

            for node in iter_nodes(body):
                if node.type != "call_expression":
                    continue

                call_name = ".".join(call_callee_parts(text, node))
                if call_name not in SPAWN_CALL_NAMES:
                    continue

                args = call_arguments(node)
                if not args:
                    continue

                argv_arg = None
                if call_name == "Gio.Subprocess.new":
                    argv_arg = args[0]
                elif call_name in {
                    "GLib.spawn_command_line_async",
                    "GLib.spawn_command_line_sync",
                }:
                    argv_arg = args[0]
                elif call_name in {"GLib.spawn_async", "GLib.spawn_async_with_pipes"}:
                    if len(args) > 1:
                        argv_arg = args[1]
                elif call_name.startswith("Shell.Util."):
                    argv_arg = args[0]

                if argv_arg is None or argv_arg.type != "identifier":
                    continue

                if identifier_name(text, argv_arg) == argv_param:
                    wrappers.add(name)
                    break

    return wrappers


class SubprocessRule(FileRule):
    """FileRule: EGO024/EGO028 — privileged and synchronous subprocess calls."""

    def check(self, root: Node, text: str, ctx: CheckContext) -> None:
        privileged_evidences: list[Evidence] = []
        sync_evidences: list[Evidence] = []
        wrapper_functions = _argv_spawn_wrapper_functions(text, root)

        for node in iter_nodes(root):
            if node.type != "call_expression":
                continue

            call_name = ".".join(call_callee_parts(text, node))
            if "shell" in ctx.file_contexts and (
                call_name in _SHELL_SYNC_SPAWN_CALL_NAMES
            ):
                sync_evidences.append(ctx.node_evidence(text, node))

            if (
                call_name not in SPAWN_CALL_NAMES
                and call_name != "GLib.shell_parse_argv"
                and call_name not in wrapper_functions
                and call_name not in _PRIVILEGED_WRAPPER_CALL_NAMES
            ):
                continue

            if call_name == "GLib.shell_parse_argv":
                args = call_arguments(node)
                command = extract_literal_string(text, args[0]) if args else None
                argv = command.split() if command is not None else None
                command_head = argv[0] if argv else None
            elif call_name in _PRIVILEGED_WRAPPER_CALL_NAMES:
                args = call_arguments(node)
                argv = extract_literal_argv(text, args[0]) if args else None
                command_head = (
                    extract_literal_argv_head(text, args[0]) if args else None
                )
            elif call_name in wrapper_functions:
                args = call_arguments(node)
                argv = extract_literal_argv(text, args[0]) if args else None
                command_head = (
                    extract_literal_argv_head(text, args[0]) if args else None
                )
            else:
                argv = extract_spawn_argv(text, node)
                command_head = argv[0] if argv else None

            if not argv and command_head is None:
                continue

            if command_head in _NON_PKEXEC_PRIVILEGE_COMMANDS:
                privileged_evidences.append(ctx.node_evidence(text, node))

        if privileged_evidences:
            ctx.add_finding(
                R.EGO024,
                (
                    "Privileged subprocess patterns must use `pkexec`, not "
                    "`sudo`, `su`, `doas`, or similar wrappers."
                ),
                privileged_evidences,
            )

        if sync_evidences:
            ctx.add_finding(
                R.EGO028,
                (
                    "Shell code should avoid synchronous subprocess APIs like "
                    "`GLib.spawn_command_line_sync()` and `GLib.spawn_sync()`."
                ),
                sync_evidences,
            )
