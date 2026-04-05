# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Callable

from tree_sitter import Node

from ..ast import (
    call_arguments,
    call_callee_parts,
    identifier_name,
    iter_nodes,
    member_expression_parts,
    top_level_function_methods,
)
from ..models import Evidence
from ..spec import R
from .context import CheckContext
from .engine import FileRule
from .spawn import (
    SPAWN_CALL_NAMES,
    extract_literal_argv,
    extract_literal_argv_head,
    extract_literal_string,
    extract_spawn_argv,
)

NON_PKEXEC_PRIVILEGE_COMMANDS = {"sudo", "su", "doas", "run0"}
PRIVILEGED_WRAPPER_CALL_NAMES = {"runProcess"}
SHELL_SYNC_SPAWN_CALL_NAMES = {
    "GLib.spawn_command_line_sync",
    "GLib.spawn_sync",
}
SHELL_SYNC_FILE_IO_CALL_NAMES = {
    "GLib.file_get_contents",
}
EXTENSION_LOOKUP_CALL_NAMES = {
    "Extension.lookupByURL",
    "Extension.lookupByUUID",
    "ExtensionPreferences.lookupByURL",
    "ExtensionPreferences.lookupByUUID",
}
GNOME49_SIGNAL_REMOVED_CLASSES = {
    "Clutter.ClickAction",
    "Clutter.TapAction",
}
GNOME50_REMOVED_DISPLAY_SIGNALS = {
    "restart",
    "show-restart-message",
}


def check_subprocess_calls(
    ctx: CheckContext,
    text: str,
    root: Node,
    contexts: set[str],
) -> None:
    privileged_evidences: list[Evidence] = []
    sync_evidences: list[Evidence] = []
    wrapper_functions = _argv_spawn_wrapper_functions(text, root)
    for node in iter_nodes(root):
        if node.type != "call_expression":
            continue

        call_name = ".".join(call_callee_parts(text, node))
        if "shell" in contexts and call_name in SHELL_SYNC_SPAWN_CALL_NAMES:
            sync_evidences.append(ctx.node_evidence(text, node))

        if (
            call_name not in SPAWN_CALL_NAMES
            and call_name != "GLib.shell_parse_argv"
            and call_name not in wrapper_functions
            and call_name not in PRIVILEGED_WRAPPER_CALL_NAMES
        ):
            continue

        if call_name == "GLib.shell_parse_argv":
            args = call_arguments(node)
            command = extract_literal_string(text, args[0]) if args else None
            argv = command.split() if command is not None else None
            command_head = argv[0] if argv else None
        elif call_name in PRIVILEGED_WRAPPER_CALL_NAMES:
            args = call_arguments(node)
            argv = extract_literal_argv(text, args[0]) if args else None
            command_head = extract_literal_argv_head(text, args[0]) if args else None
        elif call_name in wrapper_functions:
            args = call_arguments(node)
            argv = extract_literal_argv(text, args[0]) if args else None
            command_head = extract_literal_argv_head(text, args[0]) if args else None
        else:
            argv = extract_spawn_argv(text, node)
            command_head = argv[0] if argv else None
        if not argv and command_head is None:
            continue

        if command_head in NON_PKEXEC_PRIVILEGE_COMMANDS:
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


def check_api_misuse(
    ctx: CheckContext,
    text: str,
    root: Node,
    contexts: set[str],
) -> None:
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
        if "shell" in contexts and (
            call_name in SHELL_SYNC_FILE_IO_CALL_NAMES
            or call_name.endswith(".load_contents")
            or call_name.endswith(".load_bytes")
        ):
            sync_io_evidences.append(ctx.node_evidence(text, node))

        if call_name.endswith(".run_dispose") or call_name == "run_dispose":
            run_dispose_evidences.append(ctx.node_evidence(text, node))

        if call_name in EXTENSION_LOOKUP_CALL_NAMES:
            extension_lookup_evidences.append(ctx.node_evidence(text, node))

        if "shell" not in contexts or not call_name.endswith(
            (".load_stylesheet", ".unload_stylesheet")
        ):
            continue

        args = call_arguments(node)
        if not args:
            continue

        arg_text = args[0].text.decode("utf-8")
        literal = extract_literal_string(text, args[0])
        if literal == "stylesheet.css" or arg_text in stylesheet_aliases:
            stylesheet_evidences.append(ctx.node_evidence(text, node))

    if run_dispose_evidences:
        ctx.add_finding(
            R.EGO029,
            "Extension code should not call `run_dispose()`.",
            run_dispose_evidences,
        )

    if sync_io_evidences:
        ctx.add_finding(
            R.EGO030,
            (
                "Shell code should avoid synchronous file IO APIs like "
                "`GLib.file_get_contents()` and `Gio.File.load_contents()`."
            ),
            sync_io_evidences,
        )

    if stylesheet_evidences:
        ctx.add_finding(
            R.EGO034,
            (
                "Extensions should not manually load or unload the default "
                "`stylesheet.css`; GNOME Shell handles it automatically."
            ),
            stylesheet_evidences,
        )

    if extension_lookup_evidences:
        ctx.add_finding(
            R.EGO036,
            (
                "Use `this`, `this.getSettings()` or `this.path` instead of "
                "`lookupByURL()` or `lookupByUUID()` for the current "
                "extension."
            ),
            extension_lookup_evidences,
        )


def _append_removed_api_findings(
    ctx: CheckContext,
    text: str,
    root: Node,
    checks: list[tuple[str, str, Callable[[str, Node], bool]]],
) -> None:
    evidence_by_rule: dict[str, list[Evidence]] = {
        rule_id: [] for rule_id, _message, _matcher in checks
    }

    for node in iter_nodes(root):
        for rule_id, _message, matcher in checks:
            if matcher(text, node):
                evidence_by_rule[rule_id].append(ctx.node_evidence(text, node))

    for rule_id, message, _matcher in checks:
        evidences = evidence_by_rule[rule_id]
        if not evidences:
            continue

        ctx.add_finding(rule_id, message, evidences)


def _is_removed_clutter_action(source: str, node: Node) -> bool:
    if node.type != "new_expression":
        return False

    constructor = node.child_by_field_name("constructor")
    if constructor is None:
        return False

    constructor_name = ".".join(member_expression_parts(source, constructor))
    return constructor_name in GNOME49_SIGNAL_REMOVED_CLASSES


def _uses_removed_maximize_flags(source: str, node: Node) -> bool:
    if node.type != "call_expression":
        return False

    call_name = ".".join(call_callee_parts(source, node))
    if not (
        call_name.endswith(".maximize")
        or call_name.endswith(".unmaximize")
        or call_name in {"maximize", "unmaximize"}
    ):
        return False

    return any(
        ".".join(member_expression_parts(source, arg)).startswith("Meta.MaximizeFlags")
        for arg in call_arguments(node)
    )


def _calls_removed_method(source: str, node: Node, suffixes: set[str]) -> bool:
    if node.type != "call_expression":
        return False

    call_name = ".".join(call_callee_parts(source, node))
    return any(call_name.endswith(suffix) or call_name == suffix for suffix in suffixes)


def check_version_compatibility(
    ctx: CheckContext,
    text: str,
    root: Node,
    js_imports,
    target_versions: set[int],
) -> None:
    if 49 in target_versions:
        for item in js_imports:
            if (
                item.module == "resource:///org/gnome/shell/ui/calendar.js"
                and "DoNotDisturbSwitch" in item.snippet
            ):
                ctx.add_finding(
                    R.EGO_C49_001,
                    (
                        "This extension explicitly targets GNOME Shell "
                        "49 but still imports `DoNotDisturbSwitch` from "
                        "`calendar.js`."
                    ),
                    [ctx.import_evidence(item)],
                )

        _append_removed_api_findings(
            ctx,
            text,
            root,
            [
                (
                    R.EGO_C49_002,
                    (
                        "This extension explicitly targets GNOME Shell 49 "
                        "but still uses removed `Clutter.ClickAction` or "
                        "`Clutter.TapAction`."
                    ),
                    _is_removed_clutter_action,
                ),
                (
                    R.EGO_C49_003,
                    (
                        "This extension explicitly targets GNOME Shell 49 "
                        "but still passes `Meta.MaximizeFlags` to "
                        "`maximize()` or `unmaximize()`."
                    ),
                    _uses_removed_maximize_flags,
                ),
                (
                    R.EGO_C49_004,
                    (
                        "This extension explicitly targets GNOME Shell 49 "
                        "but still calls removed "
                        "`Meta.Window.get_maximized()`."
                    ),
                    lambda source, node: _calls_removed_method(
                        source,
                        node,
                        {"get_maximized"},
                    ),
                ),
                (
                    R.EGO_C49_005,
                    (
                        "This extension explicitly targets GNOME Shell 49 "
                        "but still calls removed "
                        "`Meta.CursorTracker.set_pointer_visible()`."
                    ),
                    lambda source, node: _calls_removed_method(
                        source,
                        node,
                        {"set_pointer_visible"},
                    ),
                ),
            ],
        )

    if 50 not in target_versions:
        return

    imports_run_dialog = any(
        item.module == "resource:///org/gnome/shell/ui/runDialog.js"
        for item in js_imports
    )
    _append_removed_api_findings(
        ctx,
        text,
        root,
        [
            (
                R.EGO_C50_001,
                (
                    "This extension explicitly targets GNOME Shell 50 but "
                    "still relies on removed `global.display` "
                    "restart-related signals."
                ),
                lambda source, node: _connects_removed_display_signal(source, node),
            ),
            (
                R.EGO_C50_002,
                (
                    "This extension explicitly targets GNOME Shell 50 but "
                    "still calls `RunDialog._restart()`."
                ),
                lambda source, node: imports_run_dialog
                and _calls_removed_method(source, node, {"_restart"}),
            ),
        ],
    )


def _connects_removed_display_signal(source: str, node: Node) -> bool:
    if node.type != "call_expression":
        return False

    call_name = ".".join(call_callee_parts(source, node))
    if not (
        call_name.startswith("global.display.")
        and call_name.split(".")[-1] == "connect"
    ):
        return False

    args = call_arguments(node)
    if not args:
        return False

    signal = extract_literal_string(source, args[0])
    return signal in GNOME50_REMOVED_DISPLAY_SIGNALS


# ---------------------------------------------------------------------------
# FileRule wrappers — consumed by JSFileEngine in js.py
# ---------------------------------------------------------------------------


class SubprocessRule(FileRule):
    """FileRule: checks for privileged and synchronous subprocess calls."""

    def check(self, root: Node, text: str, ctx: CheckContext) -> None:
        check_subprocess_calls(ctx, text, root, ctx.file_contexts)


class ApiMisuseRule(FileRule):
    """FileRule: checks for run_dispose, sync IO, stylesheet misuse,
    and extension lookup."""

    def check(self, root: Node, text: str, ctx: CheckContext) -> None:
        check_api_misuse(ctx, text, root, ctx.file_contexts)


class VersionCompatRule(FileRule):
    """FileRule: checks for compatibility issues with targeted GNOME Shell versions."""

    def __init__(self, js_imports: list) -> None:
        self._js_imports = js_imports

    def check(self, root: Node, text: str, ctx: CheckContext) -> None:
        check_version_compatibility(
            ctx, text, root, self._js_imports, ctx.target_versions
        )
