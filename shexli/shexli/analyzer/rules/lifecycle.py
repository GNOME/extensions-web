# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from tree_sitter import Node

from ...ast import (
    call_callee_parts,
    connect_callback_methods_for_events,
    default_export_class_methods,
    iter_nodes,
    legacy_entrypoint_methods,
    member_expression_parts,
    top_level_class_methods,
    top_level_class_names,
    top_level_class_superclasses,
    top_level_function_methods,
    top_level_variable_names,
)
from ...api_data import API
from ...spec import R
from ..context import CheckContext
from ..engine import FileRule
from ..lifecycle import (
    collect_cleanup_from_methods,
    collect_destroyable_class_names,
    collect_pre_enable_evidence,
    collect_resources_from_methods,
    collect_signal_manager_fields,
    method_reachability,
)
from ..lifecycle.base import JS_BUILTIN_CONTAINERS, SOURCE_ADD_NAMES
from ..lifecycle.rules import append_lifecycle_findings
from ..reachability import ENTRYPOINT_CONTEXTS

# Framework root superclasses whose GObject-root fields are managed by the
# framework itself (PopupMenu pattern).
_FRAMEWORK_ROOT_SUPERCLASSES = API.lifecycle.framework_root_superclasses


# ---------------------------------------------------------------------------
# Private helpers (formerly in js.py)
# ---------------------------------------------------------------------------


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


def _inherits_from(
    class_name: str,
    class_superclasses: dict[str, str],
    targets: frozenset[str],
) -> bool:
    current = class_name
    seen: set[str] = set()

    while current not in seen:
        seen.add(current)
        superclass = class_superclasses.get(current)
        if superclass is None:
            return False
        if superclass in targets:
            return True
        current = superclass

    return False


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


# ---------------------------------------------------------------------------
# Rule
# ---------------------------------------------------------------------------


def _check_class_lifecycle(
    text: str,
    class_name: str,
    class_methods: dict[str, list],
    class_superclasses: dict[str, str],
    destroyable_classes: set[str],
    ctx: CheckContext,
) -> None:
    class_enable_methods = method_reachability(
        text,
        class_methods,
        ["constructor", "_init", "enable"],
    )
    cleanup_start_names = [
        "disable",
        "destroy",
        "_destroy",
        "dispose",
        "cleanup",
        "stop",
    ]
    for method in class_enable_methods:
        body = method.child_by_field_name("body")
        if body is None:
            continue

        for callback_name in connect_callback_methods_for_events(
            text,
            body,
            {"destroy"},
        ):
            if callback_name not in cleanup_start_names:
                cleanup_start_names.append(callback_name)

    class_disable_methods = method_reachability(
        text,
        class_methods,
        cleanup_start_names,
    )
    if not class_enable_methods:
        return

    class_signal_manager_fields = collect_signal_manager_fields(
        text,
        class_enable_methods,
        destroyable_classes,
        set(),
    )
    class_created = collect_resources_from_methods(
        text,
        ctx.path,
        class_enable_methods,
        ctx.mapper,
        destroyable_classes,
        set(),
        class_signal_manager_fields,
    )
    class_cleaned = collect_cleanup_from_methods(
        text,
        class_disable_methods,
        set(),
        set(class_created.signal_groups) | class_signal_manager_fields,
    )
    suppress_root_fields: set[str] = set()
    if class_name in _FRAMEWORK_ROOT_SUPERCLASSES or _inherits_from(
        class_name,
        class_superclasses,
        _FRAMEWORK_ROOT_SUPERCLASSES,
    ):
        suppress_root_fields.update({"actor", "box", "menu"})
    append_lifecycle_findings(
        ctx.findings,
        class_created,
        class_cleaned,
        include_object_cleanup=class_name not in destroyable_classes,
        release_container_names=set(),
        suppress_root_fields=suppress_root_fields,
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
            R.EGO037,
            "Soup.Session instances should be aborted during cleanup.",
            [
                ctx.node_evidence(text, class_soup_session_fields[name][0])
                for name in missing_class_soup_abort
            ],
        )


class LifecycleRule(FileRule):
    """
    FileRule: lifecycle analysis for entrypoint and non-entrypoint classes.

    Covers EGO013 (pre-enable resources), EGO014–EGO016/EGO027 (lifecycle
    cleanup via append_lifecycle_findings), EGO035 (source recreation), and
    EGO037 (Soup.Session abort).
    """

    def check(self, root: Node, text: str, ctx: CheckContext) -> None:
        if ctx.path.name not in ENTRYPOINT_CONTEXTS:
            methods: dict[str, list] = {}
        else:
            methods = default_export_class_methods(
                text, root
            ) or legacy_entrypoint_methods(text, root)
            top_level_methods = top_level_function_methods(text, root)
            if methods:
                for name, nodes in top_level_methods.items():
                    methods.setdefault(name, []).extend(nodes)

        module_vars = top_level_variable_names(text, root)
        destroyable_classes = collect_destroyable_class_names(text, root)
        local_class_names = top_level_class_names(text, root)

        _reachability_cache: dict[tuple[str, ...], list] = {}

        def _reachable(start_names: list[str]) -> list:
            key = tuple(start_names)
            if key not in _reachability_cache:
                _reachability_cache[key] = method_reachability(
                    text, methods, start_names
                )
            return _reachability_cache[key]

        enable_methods = _reachable(["enable"])
        disable_methods = _reachable(["disable"])
        signal_manager_fields = collect_signal_manager_fields(
            text,
            _reachable(["constructor", "_init", "enable"]),
            destroyable_classes,
            module_vars,
        )

        created = collect_resources_from_methods(
            text,
            ctx.path,
            enable_methods,
            ctx.mapper,
            destroyable_classes,
            module_vars,
            signal_manager_fields,
        )
        cleaned = collect_cleanup_from_methods(
            text,
            disable_methods,
            module_vars,
            set(created.signal_groups) | signal_manager_fields,
        )
        pre_enable_evidence = collect_pre_enable_evidence(
            text, ctx.path, root, methods, ctx.mapper
        )
        constructor_custom_refs = _entrypoint_constructor_custom_refs(
            text,
            _reachable(["constructor", "_init"]),
            local_class_names,
            set(cleaned.touched_refs) | set(cleaned.released_refs),
            ctx,
        )
        pre_enable_evidence.extend(constructor_custom_refs.values())
        if pre_enable_evidence:
            ctx.add_finding(
                R.EGO013,
                (
                    "Resource creation or signal/source setup was found "
                    "outside `enable()`."
                ),
                pre_enable_evidence[:10],
            )
        constructor_created = collect_resources_from_methods(
            text,
            ctx.path,
            _reachable(["constructor", "_init"]),
            ctx.mapper,
            destroyable_classes,
            module_vars,
        )
        for name, evidence in constructor_created.resource_refs.items():
            created.resource_refs.setdefault(name, evidence)
        for name, evidence in _entrypoint_local_class_refs(
            text,
            _reachable(["constructor", "_init", "enable"]),
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
            _reachable(["constructor", "_init", "enable"]),
        )
        aborted_soup_sessions = _aborted_soup_session_fields(text, disable_methods)
        missing_soup_abort = sorted(set(soup_session_fields) - aborted_soup_sessions)
        if missing_soup_abort:
            ctx.add_finding(
                R.EGO037,
                "Soup.Session instances should be aborted during cleanup.",
                [
                    ctx.node_evidence(text, soup_session_fields[name][0])
                    for name in missing_soup_abort
                ],
            )

        entrypoint_method_nodes = {
            id(node) for method_nodes in methods.values() for node in method_nodes
        }
        class_superclasses = top_level_class_superclasses(text, root)
        for class_name, class_methods in top_level_class_methods(text, root).items():
            class_nodes = [
                node for method_nodes in class_methods.values() for node in method_nodes
            ]
            if class_nodes and all(
                id(node) in entrypoint_method_nodes for node in class_nodes
            ):
                continue

            _check_class_lifecycle(
                text,
                class_name,
                class_methods,
                class_superclasses,
                destroyable_classes,
                ctx,
            )
