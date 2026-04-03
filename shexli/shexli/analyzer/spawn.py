# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from ..ast import array_elements, call_arguments, call_callee_parts, node_text

SPAWN_CALL_NAMES = {
    "GLib.spawn_async",
    "GLib.spawn_async_with_pipes",
    "GLib.spawn_command_line_async",
    "GLib.spawn_command_line_sync",
    "Shell.Util.spawn",
    "Shell.Util.spawn_async",
    "Shell.Util.spawnCommandLine",
    "Shell.Util.trySpawn",
    "Shell.Util.trySpawnCommandLine",
    "Gio.Subprocess.new",
}


def extract_literal_string(
    source: str,
    node,
    *,
    allow_dynamic_template: bool = False,
) -> str | None:
    if node.type == "string":
        return node_text(source, node).strip("\"'")

    if node.type == "template_string" and (
        len(node.named_children) == 1 or allow_dynamic_template
    ):
        return node_text(source, node).strip("`")

    return None


def extract_literal_argv(source: str, node) -> list[str] | None:
    if node.type == "array":
        values: list[str] = []
        for child in array_elements(node):
            literal = extract_literal_string(source, child)
            if literal is None:
                return None

            values.append(literal)

        return values

    literal = extract_literal_string(source, node)
    if literal is not None:
        return literal.split()

    return None


def extract_literal_argv_head(source: str, node) -> str | None:
    if node.type == "array":
        values = array_elements(node)
        if not values:
            return None

        return extract_literal_string(source, values[0])

    literal = extract_literal_string(source, node)
    if literal is not None:
        parts = literal.split()
        return parts[0] if parts else None

    return None


def extract_spawn_argv(source: str, node) -> list[str] | None:
    call_name = ".".join(call_callee_parts(source, node))
    args = call_arguments(node)

    if call_name == "Gio.Subprocess.new" and args:
        return extract_literal_argv(source, args[0])

    if (
        call_name in {"GLib.spawn_command_line_async", "GLib.spawn_command_line_sync"}
        and args
    ):
        return extract_literal_argv(source, args[0])

    if (
        call_name in {"GLib.spawn_async", "GLib.spawn_async_with_pipes"}
        and len(args) > 1
    ):
        return extract_literal_argv(source, args[1])

    if call_name.startswith("Shell.Util.") and args:
        return extract_literal_argv(source, args[0])

    return None


def extract_gjs_module_target(source: str, node) -> str | None:
    call_name = ".".join(call_callee_parts(source, node))
    args = call_arguments(node)
    argv: list[str] | None = None

    if call_name == "Gio.Subprocess.new" and args and args[0].type == "array":
        values: list[str] = []
        for child in array_elements(args[0]):
            literal = extract_literal_string(
                source,
                child,
                allow_dynamic_template=True,
            )
            if literal is None:
                return None

            values.append(literal)

        argv = values
    elif (
        call_name in {"GLib.spawn_command_line_async", "GLib.spawn_command_line_sync"}
        and args
    ):
        command = extract_literal_string(source, args[0])
        if command is not None:
            argv = command.split()
    elif (
        call_name in {"GLib.spawn_async", "GLib.spawn_async_with_pipes"}
        and len(args) > 1
        and args[1].type == "array"
    ):
        values: list[str] = []
        for child in array_elements(args[1]):
            literal = extract_literal_string(
                source,
                child,
                allow_dynamic_template=True,
            )
            if literal is None:
                return None

            values.append(literal)

        argv = values
    elif call_name.startswith("Shell.Util.") and args:
        if args[0].type == "array":
            values: list[str] = []
            for child in array_elements(args[0]):
                literal = extract_literal_string(
                    source,
                    child,
                    allow_dynamic_template=True,
                )
                if literal is None:
                    return None

                values.append(literal)

            argv = values
        else:
            command = extract_literal_string(source, args[0])
            if command is not None:
                argv = command.split()

    if not argv or len(argv) < 3 or argv[0] != "gjs" or argv[1] != "-m":
        return None

    return argv[2]
