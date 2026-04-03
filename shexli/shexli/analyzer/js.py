# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from ..ast import (
    call_arguments,
    call_callee_parts,
    default_export_class_methods,
    imports_in_program,
    iter_nodes,
    legacy_entrypoint_methods,
    legacy_imports_in_program,
    member_expression_parts,
    node_text,
    parse_js,
    top_level_class_methods,
    top_level_class_names,
    top_level_function_methods,
    top_level_variable_names,
)
from .compat import (
    check_api_misuse,
    check_subprocess_calls,
    check_version_compatibility,
)
from .context import CheckContext
from .lifecycle import (
    collect_cleanup_from_methods,
    collect_destroyable_class_names,
    collect_pre_enable_evidence,
    collect_resources_from_methods,
    method_reachability,
)
from .lifecycle.base import JS_BUILTIN_CONTAINERS, SOURCE_ADD_NAMES
from .lifecycle.rules import append_lifecycle_findings
from .reachability import ENTRYPOINT_CONTEXTS

DEPRECATED_IMPORT_TOKENS = ("ByteArray", "Lang", "Mainloop")
SHELL_FORBIDDEN_TOKENS = {"Gtk", "Gdk", "Adw"}
PREFS_FORBIDDEN_TOKENS = {"Clutter", "Meta", "St", "Shell"}


def _prefs_retained_field_name(text: str, node) -> str | None:
    if node.type != "assignment_expression":
        return None

    left = node.child_by_field_name("left")
    if left is None:
        return None

    parts = member_expression_parts(text, left)
    if len(parts) == 2 and parts[0] == "this":
        return parts[1]

    return None


def _prefs_retained_value_node(node):
    if node.type != "assignment_expression":
        return None

    return node.child_by_field_name("right")


def _prefs_retains_window_objects(
    text: str,
    methods: dict[str, list],
    ctx: CheckContext,
):
    retained_evidences = []
    fill_methods = method_reachability(text, methods, ["fillPreferencesWindow"])
    if not fill_methods:
        return retained_evidences

    has_close_request_cleanup = False
    for method in fill_methods:
        body = method.child_by_field_name("body")
        if body is None:
            continue

        for node in iter_nodes(body):
            if node.type == "call_expression":
                call_name = ".".join(call_callee_parts(text, node))
                if call_name.endswith(".connect"):
                    args = call_arguments(node)
                    if (
                        len(args) >= 2
                        and args[0].type == "string"
                        and node_text(text, args[0]).strip("\"'") == "close-request"
                    ):
                        has_close_request_cleanup = True

            field = _prefs_retained_field_name(text, node)
            if not field:
                continue

            value = _prefs_retained_value_node(node)
            if value is None or value.type not in {"new_expression", "call_expression"}:
                continue

            retained_evidences.append(ctx.node_evidence(text, node))

    if has_close_request_cleanup:
        return []

    return retained_evidences


def legacy_import_hits(text: str, token: str) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        normalized = line.replace(" ", "")
        if f"imports.{token.lower()}" in normalized.lower():
            hits.append((idx, line.strip()))

    return hits


def imports_gi_hits(text: str) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        normalized = line.replace(" ", "")
        if "imports._gi" in normalized:
            hits.append((idx, line.strip()))

    return hits


def _soup_session_fields(text: str, methods: list) -> dict[str, list]:
    fields: dict[str, list] = {}

    for method in methods:
        body = method.child_by_field_name("body")
        if body is None:
            continue

        for node in iter_nodes(body):
            if node.type != "assignment_expression":
                continue

            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if left is None or right is None or right.type != "new_expression":
                continue

            parts = member_expression_parts(text, left)
            if len(parts) != 2 or parts[0] != "this":
                continue

            constructor = right.child_by_field_name("constructor")
            if constructor is None:
                continue

            if ".".join(member_expression_parts(text, constructor)) != "Soup.Session":
                continue

            fields.setdefault(parts[1], []).append(node)

    return fields


def _aborted_soup_session_fields(text: str, methods: list) -> set[str]:
    fields: set[str] = set()

    for method in methods:
        body = method.child_by_field_name("body")
        if body is None:
            continue

        for node in iter_nodes(body):
            if node.type != "call_expression":
                continue

            function_node = node.child_by_field_name("function")
            if function_node is None:
                continue

            parts = member_expression_parts(text, function_node)
            if len(parts) == 3 and parts[0] == "this" and parts[2] == "abort":
                fields.add(parts[1])

    return fields


def _entrypoint_local_class_refs(
    text: str,
    methods: list,
    local_class_names: set[str],
    ctx: CheckContext,
) -> dict[str, object]:
    refs = {}

    for method in methods:
        body = method.child_by_field_name("body")
        if body is None:
            continue

        for node in iter_nodes(body):
            if node.type != "assignment_expression":
                continue

            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if left is None or right is None:
                continue

            left_parts = member_expression_parts(text, left)
            if len(left_parts) != 2 or left_parts[0] != "this":
                continue

            if right.type == "new_expression":
                constructor = right.child_by_field_name("constructor")
                if constructor is None:
                    continue

                constructor_parts = member_expression_parts(text, constructor)
                if len(constructor_parts) != 1:
                    continue

                if constructor_parts[0] not in local_class_names:
                    continue
            elif right.type == "call_expression":
                if not ".".join(call_callee_parts(text, right)).endswith(".new"):
                    continue
            else:
                continue

            refs.setdefault(left_parts[1], ctx.node_evidence(text, node))

    return refs


def _entrypoint_constructor_custom_refs(
    text: str,
    methods: list,
    local_class_names: set[str],
    cleanup_touched_fields: set[str],
    ctx: CheckContext,
) -> dict[str, object]:
    refs = {}

    for method in methods:
        body = method.child_by_field_name("body")
        if body is None:
            continue

        for node in iter_nodes(body):
            if node.type != "assignment_expression":
                continue

            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if left is None or right is None or right.type != "new_expression":
                continue

            left_parts = member_expression_parts(text, left)
            if len(left_parts) != 2 or left_parts[0] != "this":
                continue

            field = left_parts[1]
            if field not in cleanup_touched_fields:
                continue

            constructor = right.child_by_field_name("constructor")
            if constructor is None:
                continue

            constructor_parts = member_expression_parts(text, constructor)
            constructor_name = ".".join(constructor_parts)
            if not constructor_parts:
                continue

            if constructor_name in JS_BUILTIN_CONTAINERS:
                continue

            if len(constructor_parts) != 1:
                continue

            if constructor_parts[0] in local_class_names:
                continue

            refs.setdefault(field, ctx.node_evidence(text, node))

    return refs


def _entrypoint_runtime_anonymous_sources(
    text: str,
    methods: dict[str, list],
    ctx: CheckContext,
) -> dict[str, object]:
    sources = {}
    cleanup_methods = {"disable", "destroy", "_destroy", "dispose", "cleanup", "stop"}

    for method_name, method_nodes in methods.items():
        if method_name in cleanup_methods:
            continue

        for method in method_nodes:
            body = method.child_by_field_name("body")
            if body is None:
                continue

            for node in iter_nodes(body):
                if node.type != "call_expression":
                    continue

                if ".".join(call_callee_parts(text, node)) not in SOURCE_ADD_NAMES:
                    continue

                if node.parent is None or node.parent.type != "expression_statement":
                    continue

                key = f"anonymous-source:{node.start_point.row + 1}"
                sources.setdefault(key, ctx.node_evidence(text, node))

    return sources


def _check_forbidden_imports(
    rule_id: str,
    ctx: CheckContext,
    js_imports,
    forbidden_tokens: set[str],
    message_template: str,
) -> None:
    for item in js_imports:
        token = None
        if item.module and item.module.startswith("gi://"):
            token = item.module.removeprefix("gi://").split("?")[0]

        if token in forbidden_tokens:
            ctx.add_finding(
                rule_id,
                message_template.format(token=token),
                [ctx.import_evidence(item)],
            )


def check_js_file(
    ctx: CheckContext,
    text: str,
    metadata: dict | None,
    target_versions: set[int],
    contexts: set[str],
) -> None:
    is_prefs = "prefs" in contexts
    is_shell = "shell" in contexts
    path = ctx.path
    mapper = ctx.mapper

    tree = parse_js(text)
    root = tree.root_node
    js_imports = imports_in_program(text, root) + legacy_imports_in_program(text, root)

    for token in DEPRECATED_IMPORT_TOKENS:
        evidences = []

        for item in js_imports:
            if item.module in {f"gi://{token}", f"imports.{token.lower()}"} or any(
                token in name for name in item.names
            ):
                evidences.append(ctx.import_evidence(item))

        evidences.extend(
            ctx.display_evidence(line=line, snippet=snippet[:300])
            for line, snippet in legacy_import_hits(text, token)
        )

        if evidences:
            ctx.add_finding(
                "EGO017",
                f"Deprecated module `{token}` is imported.",
                evidences,
            )

    imports_gi_evidences = [
        ctx.display_evidence(line=line, snippet=snippet[:300])
        for line, snippet in imports_gi_hits(text)
    ]
    if imports_gi_evidences:
        ctx.add_finding(
            "EGO031",
            "Direct use of `imports._gi` is discouraged in extensions.",
            imports_gi_evidences,
        )

    if is_shell:
        _check_forbidden_imports(
            "EGO018",
            ctx,
            js_imports,
            SHELL_FORBIDDEN_TOKENS,
            "GTK library `{token}` must not be imported in shell process files.",
        )

    if is_prefs:
        _check_forbidden_imports(
            "EGO019",
            ctx,
            js_imports,
            PREFS_FORBIDDEN_TOKENS,
            "GNOME Shell library `{token}` must not be imported in preferences files.",
        )

    if path.name in ENTRYPOINT_CONTEXTS:
        methods = default_export_class_methods(text, root) or legacy_entrypoint_methods(
            text,
            root,
        )
        top_level_methods = top_level_function_methods(text, root)
        if methods:
            for name, nodes in top_level_methods.items():
                methods.setdefault(name, []).extend(nodes)
    else:
        methods = {}
        top_level_methods = {}

    if path.name == "prefs.js" and any(version >= 45 for version in target_versions):
        prefs_widget_evidences = []
        for method in methods.get("getPreferencesWidget", []) or top_level_methods.get(
            "getPreferencesWidget", []
        ):
            prefs_widget_evidences.append(ctx.node_evidence(text, method))

        if prefs_widget_evidences:
            ctx.add_finding(
                "EGO032",
                (
                    "45+ preferences code should use `fillPreferencesWindow()` "
                    "instead of `getPreferencesWidget()`."
                ),
                prefs_widget_evidences,
            )

    if path.name == "prefs.js":
        prefs_retained_evidences = _prefs_retains_window_objects(text, methods, ctx)
        if prefs_retained_evidences:
            ctx.add_finding(
                "EGO033",
                (
                    "Preferences code stores window-scoped objects on the "
                    "exported prefs class without `close-request` cleanup."
                ),
                prefs_retained_evidences[:10],
            )

    module_vars = top_level_variable_names(text, root)
    enable_methods = method_reachability(text, methods, ["enable"])
    disable_methods = method_reachability(text, methods, ["disable"])
    destroyable_classes = collect_destroyable_class_names(text, root)
    local_class_names = top_level_class_names(text, root)
    cleaned = collect_cleanup_from_methods(text, disable_methods, module_vars)

    pre_enable_evidence = collect_pre_enable_evidence(text, path, root, methods, mapper)
    constructor_custom_refs = _entrypoint_constructor_custom_refs(
        text,
        method_reachability(text, methods, ["constructor", "_init"]),
        local_class_names,
        set(cleaned.touched_refs) | set(cleaned.released_refs),
        ctx,
    )
    pre_enable_evidence.extend(constructor_custom_refs.values())
    if pre_enable_evidence:
        ctx.add_finding(
            "EGO013",
            (
                "Resource creation or signal/source setup was found "
                "outside `enable()`."
            ),
            pre_enable_evidence[:10],
        )

    created = collect_resources_from_methods(
        text,
        path,
        enable_methods,
        mapper,
        destroyable_classes,
        module_vars,
    )
    constructor_created = collect_resources_from_methods(
        text,
        path,
        method_reachability(text, methods, ["constructor", "_init"]),
        mapper,
        destroyable_classes,
        module_vars,
    )
    for name, evidence in constructor_created.resource_refs.items():
        created.resource_refs.setdefault(name, evidence)
    for name, evidence in _entrypoint_local_class_refs(
        text,
        method_reachability(text, methods, ["constructor", "_init", "enable"]),
        local_class_names,
        ctx,
    ).items():
        created.resource_refs.setdefault(name, evidence)
    for name, evidence in constructor_custom_refs.items():
        created.resource_refs.setdefault(name, evidence)
    for name, evidence in _entrypoint_runtime_anonymous_sources(
        text,
        methods,
        ctx,
    ).items():
        created.sources.setdefault(name, evidence)
    append_lifecycle_findings(
        ctx.findings,
        created,
        cleaned,
        release_container_names=module_vars,
    )
    soup_session_fields = _soup_session_fields(
        text,
        method_reachability(text, methods, ["constructor", "_init", "enable"]),
    )
    aborted_soup_sessions = _aborted_soup_session_fields(text, disable_methods)
    missing_soup_abort = sorted(set(soup_session_fields) - aborted_soup_sessions)
    if missing_soup_abort:
        ctx.add_finding(
            "EGO037",
            "Soup.Session instances should be aborted during cleanup.",
            [
                ctx.node_evidence(text, soup_session_fields[name][0])
                for name in missing_soup_abort
            ],
        )

    entrypoint_method_nodes = {
        id(node) for method_nodes in methods.values() for node in method_nodes
    }
    for class_name, class_methods in top_level_class_methods(text, root).items():
        class_nodes = [
            node for method_nodes in class_methods.values() for node in method_nodes
        ]
        if class_nodes and all(
            id(node) in entrypoint_method_nodes for node in class_nodes
        ):
            continue

        class_enable_methods = method_reachability(
            text,
            class_methods,
            ["constructor", "_init", "enable"],
        )
        class_disable_methods = method_reachability(
            text,
            class_methods,
            ["disable", "destroy", "_destroy", "dispose", "cleanup", "stop"],
        )
        if not class_enable_methods:
            continue

        class_created = collect_resources_from_methods(
            text,
            path,
            class_enable_methods,
            mapper,
            destroyable_classes,
            set(),
        )
        class_cleaned = collect_cleanup_from_methods(
            text,
            class_disable_methods,
            set(),
        )
        append_lifecycle_findings(
            ctx.findings,
            class_created,
            class_cleaned,
            include_object_cleanup=class_name not in destroyable_classes,
            release_container_names=set(),
        )
        class_soup_session_fields = _soup_session_fields(text, class_enable_methods)
        class_aborted_soup_sessions = _aborted_soup_session_fields(
            text,
            class_disable_methods,
        )
        missing_class_soup_abort = sorted(
            set(class_soup_session_fields) - class_aborted_soup_sessions
        )
        if missing_class_soup_abort:
            ctx.add_finding(
                "EGO037",
                "Soup.Session instances should be aborted during cleanup.",
                [
                    ctx.node_evidence(text, class_soup_session_fields[name][0])
                    for name in missing_class_soup_abort
                ],
            )

    if (
        path.name == "extension.js"
        and "shell" in contexts
        and metadata
        and metadata.get("session-modes")
        and "unlock-dialog" in metadata["session-modes"]
    ):
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
                "EGO008",
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

    check_subprocess_calls(ctx, text, root, contexts)
    check_api_misuse(ctx, text, root, contexts)
    check_version_compatibility(
        ctx,
        text,
        root,
        js_imports,
        target_versions,
    )
