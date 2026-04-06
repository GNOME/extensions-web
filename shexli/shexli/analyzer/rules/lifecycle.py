# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass

from tree_sitter import Node

from ...api_data import API
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
from ...models import Evidence
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
from ..lifecycle.types import CrossFileIndex
from ..reachability import ENTRYPOINT_CONTEXTS

# GObject root superclasses whose fields (actor, box, menu) are managed by
# the framework itself — suppress those from lifecycle findings.
_FRAMEWORK_ROOT_SUPERCLASSES = API.lifecycle.framework_root_superclasses

# ---------------------------------------------------------------------------
# AST helpers — pure functions, no class context required
# ---------------------------------------------------------------------------


def _soup_session_fields(text: str, methods: list) -> dict[str, list]:
    """Return {field_name: [node]} for `this.field = new Soup.Session()` assignments."""
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
    """Return the set of field names where `this.field.abort()` is called."""
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


def _check_soup_abort(
    text: str,
    enable_methods: list,
    disable_methods: list,
    ctx: CheckContext,
) -> None:
    """EGO_L_008: Soup.Session created during enable must be aborted in cleanup."""
    session_fields = _soup_session_fields(text, enable_methods)
    aborted = _aborted_soup_session_fields(text, disable_methods)
    missing = sorted(set(session_fields) - aborted)

    if not missing:
        return

    ctx.add_finding(
        R.EGO_L_008,
        "Soup.Session instances should be aborted during cleanup.",
        [ctx.node_evidence(text, session_fields[name][0]) for name in missing],
    )


def _inherits_from(
    class_name: str,
    class_superclasses: dict[str, str],
    targets: frozenset[str],
) -> bool:
    """Walk the superclass chain; return True if class_name descends from any target."""
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


def _local_class_refs(
    text: str,
    methods: list,
    local_class_names: set[str],
    ctx: CheckContext,
) -> dict[str, Evidence]:
    """
    Collect `this.field = new LocalClass()` and `this.field = LocalClass.new()`
    assignments — local-class instances that need lifecycle tracking.
    """
    refs: dict[str, Evidence] = {}

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

                ctor_parts = member_expression_parts(text, constructor)
                if len(ctor_parts) != 1 or ctor_parts[0] not in local_class_names:
                    continue
            elif right.type == "call_expression":
                if not ".".join(call_callee_parts(text, right)).endswith(".new"):
                    continue
            else:
                continue

            refs.setdefault(left_parts[1], ctx.node_evidence(text, node))

    return refs


def _constructor_custom_refs(
    text: str,
    methods: list,
    local_class_names: set[str],
    cleanup_touched_fields: set[str],
    ctx: CheckContext,
) -> dict[str, Evidence]:
    """
    Collect `this.field = new ExternalClass()` in constructor/init when that
    field is referenced in cleanup — external-class instances that need tracking.

    Excludes JS built-in containers and locally-defined classes (handled
    separately by _local_class_refs).
    """
    refs: dict[str, Evidence] = {}

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

            field_name = left_parts[1]
            if field_name not in cleanup_touched_fields:
                continue

            constructor = right.child_by_field_name("constructor")
            if constructor is None:
                continue

            ctor_parts = member_expression_parts(text, constructor)
            if not ctor_parts or len(ctor_parts) != 1:
                continue

            if (
                ctor_parts[0] in JS_BUILTIN_CONTAINERS
                or ctor_parts[0] in local_class_names
            ):
                continue

            refs.setdefault(field_name, ctx.node_evidence(text, node))

    return refs


def _runtime_anonymous_sources(
    text: str,
    methods: dict[str, list],
    ctx: CheckContext,
) -> dict[str, Evidence]:
    """
    Detect Source.add() calls outside cleanup methods — anonymous sources
    started at runtime that may not be removed during disable().
    """
    _CLEANUP_NAMES = {"disable", "destroy", "_destroy", "dispose", "cleanup", "stop"}
    sources: dict[str, Evidence] = {}

    for method_name, method_nodes in methods.items():
        if method_name in _CLEANUP_NAMES:
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
# Entrypoint analysis
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _EntrypointState:
    """Computed facts about the extension entrypoint file."""

    methods: dict[str, list]
    module_vars: set[str]
    destroyable_classes: set[str]
    local_class_names: set[str]
    class_superclasses: dict[str, str]
    signal_manager_fields: set[str]
    cross_file_index: CrossFileIndex | None


class _EntrypointAnalyzer:
    """
    Lifecycle analysis for the extension entrypoint (extension.js / prefs.js).

    Checks:
      EGO_L_001  resources created outside enable()
      EGO_L_002–005  lifecycle cleanup completeness (via append_lifecycle_findings)
      EGO_L_007  anonymous sources added at runtime
      EGO_L_008  Soup.Session not aborted during cleanup
    """

    def __init__(self, text: str, root: Node, ctx: CheckContext) -> None:
        self.text = text
        self.root = root
        self.ctx = ctx
        self.state = self._build_state()
        self._reachability_cache: dict[tuple[str, ...], list] = {}

    def run(self) -> None:
        self._check_pre_enable()
        self._check_lifecycle()
        self._check_soup()
        self._check_nested_classes()

    # --- initialisation ---

    def _collect_methods(self) -> dict[str, list]:
        if self.ctx.path.name not in ENTRYPOINT_CONTEXTS:
            return {}

        methods = (
            default_export_class_methods(self.text, self.root)
            or legacy_entrypoint_methods(self.text, self.root)
        )
        if not methods:
            return {}

        for name, nodes in top_level_function_methods(self.text, self.root).items():
            methods.setdefault(name, []).extend(nodes)

        return methods

    def _build_state(self) -> _EntrypointState:
        methods = self._collect_methods()
        module_vars = top_level_variable_names(self.text, self.root)
        destroyable_classes = collect_destroyable_class_names(self.text, self.root)

        # signal_manager_fields needs a one-off reachability pass before the
        # cache is available (the cache itself is built in __init__ after this).
        ctor_enable = method_reachability(
            self.text, methods, ["constructor", "_init", "enable"]
        )
        signal_manager_fields = collect_signal_manager_fields(
            self.text, ctor_enable, destroyable_classes, module_vars
        )

        return _EntrypointState(
            methods=methods,
            module_vars=module_vars,
            destroyable_classes=destroyable_classes,
            local_class_names=top_level_class_names(self.text, self.root),
            class_superclasses=top_level_class_superclasses(self.text, self.root),
            signal_manager_fields=signal_manager_fields,
            cross_file_index=self.ctx.cross_file_index,
        )

    def _reachable(self, start_names: list[str]) -> list:
        """Memoised method-reachability from the given entry points."""
        key = tuple(start_names)
        if key not in self._reachability_cache:
            self._reachability_cache[key] = method_reachability(
                self.text, self.state.methods, start_names
            )

        return self._reachability_cache[key]

    # --- checks ---

    def _check_pre_enable(self) -> None:
        constructor_methods = self._reachable(["constructor", "_init"])
        cleanup = collect_cleanup_from_methods(
            self.text,
            self._reachable(["disable"]),
            self.state.module_vars,
            self.state.signal_manager_fields,
            cross_file_index=self.state.cross_file_index,
        )

        evidence = collect_pre_enable_evidence(
            self.text, self.ctx.path, self.root, self.state.methods, self.ctx.mapper
        )
        evidence.extend(
            _constructor_custom_refs(
                self.text,
                constructor_methods,
                self.state.local_class_names,
                set(cleanup.touched_refs) | set(cleanup.released_refs),
                self.ctx,
            ).values()
        )

        if evidence:
            self.ctx.add_finding(
                R.EGO_L_001,
                "Resource creation or signal/source setup was found"
                " outside `enable()`.",
                evidence[:10],
            )

    def _check_lifecycle(self) -> None:
        enable_methods = self._reachable(["enable"])
        disable_methods = self._reachable(["disable"])
        constructor_methods = self._reachable(["constructor", "_init"])
        ctor_enable_methods = self._reachable(["constructor", "_init", "enable"])

        created = collect_resources_from_methods(
            self.text,
            self.ctx.path,
            enable_methods,
            self.ctx.mapper,
            self.state.destroyable_classes,
            self.state.module_vars,
            self.state.signal_manager_fields,
            cross_file_index=self.state.cross_file_index,
        )
        cleaned = collect_cleanup_from_methods(
            self.text,
            disable_methods,
            self.state.module_vars,
            set(created.signal_groups) | self.state.signal_manager_fields,
            cross_file_index=self.state.cross_file_index,
        )

        # Merge resources visible from constructor and enable into the created set.
        for name, evidence in collect_resources_from_methods(
            self.text,
            self.ctx.path,
            constructor_methods,
            self.ctx.mapper,
            self.state.destroyable_classes,
            self.state.module_vars,
        ).resource_refs.items():
            created.resource_refs.setdefault(name, evidence)

        for name, evidence in _local_class_refs(
            self.text, ctor_enable_methods, self.state.local_class_names, self.ctx
        ).items():
            created.resource_refs.setdefault(name, evidence)

        for name, evidence in _constructor_custom_refs(
            self.text,
            constructor_methods,
            self.state.local_class_names,
            set(cleaned.touched_refs) | set(cleaned.released_refs),
            self.ctx,
        ).items():
            created.resource_refs.setdefault(name, evidence)

        for name, evidence in _runtime_anonymous_sources(
            self.text, self.state.methods, self.ctx
        ).items():
            created.sources.setdefault(name, evidence)

        append_lifecycle_findings(
            self.ctx.findings,
            created,
            cleaned,
            release_container_names=self.state.module_vars,
        )

    def _check_soup(self) -> None:
        _check_soup_abort(
            self.text,
            self._reachable(["constructor", "_init", "enable"]),
            self._reachable(["disable"]),
            self.ctx,
        )

    def _check_nested_classes(self) -> None:
        entrypoint_node_ids = {
            id(node)
            for method_nodes in self.state.methods.values()
            for node in method_nodes
        }

        for class_name, class_methods in top_level_class_methods(
            self.text, self.root
        ).items():
            class_nodes = [
                node
                for method_nodes in class_methods.values()
                for node in method_nodes
            ]
            # Skip classes whose methods are all already part of the entrypoint.
            if class_nodes and all(
                id(node) in entrypoint_node_ids for node in class_nodes
            ):
                continue

            _ClassAnalyzer(
                self.text,
                class_name,
                class_methods,
                self.state.class_superclasses,
                self.state.destroyable_classes,
                self.ctx,
            ).run()


# ---------------------------------------------------------------------------
# Non-entrypoint class analysis
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _ClassState:
    enable_methods: list
    disable_methods: list
    signal_manager_fields: set[str]


class _ClassAnalyzer:
    """
    Lifecycle analysis for GObject classes that are not the extension entrypoint.

    Checks:
      EGO_L_002–005  lifecycle cleanup completeness (via append_lifecycle_findings)
      EGO_L_008      Soup.Session not aborted during cleanup
    """

    def __init__(
        self,
        text: str,
        class_name: str,
        class_methods: dict[str, list],
        class_superclasses: dict[str, str],
        destroyable_classes: set[str],
        ctx: CheckContext,
    ) -> None:
        self.text = text
        self.class_name = class_name
        self.class_methods = class_methods
        self.class_superclasses = class_superclasses
        self.destroyable_classes = destroyable_classes
        self.ctx = ctx

    def run(self) -> None:
        state = self._build_state()
        if not state.enable_methods:
            return

        self._check_lifecycle(state)
        self._check_soup(state)

    def _build_state(self) -> _ClassState:
        enable_methods = method_reachability(
            self.text, self.class_methods, ["constructor", "_init", "enable"]
        )

        return _ClassState(
            enable_methods=enable_methods,
            disable_methods=method_reachability(
                self.text,
                self.class_methods,
                self._cleanup_start_names(enable_methods),
            ),
            signal_manager_fields=collect_signal_manager_fields(
                self.text, enable_methods, self.destroyable_classes, set()
            ),
        )

    def _cleanup_start_names(self, enable_methods: list) -> list[str]:
        """Standard cleanup entry points, plus any destroy-connected callbacks."""
        names = ["disable", "destroy", "_destroy", "dispose", "cleanup", "stop"]

        for method in enable_methods:
            body = method.child_by_field_name("body")
            if body is None:
                continue

            for callback_name in connect_callback_methods_for_events(
                self.text, body, {"destroy"}
            ):
                if callback_name not in names:
                    names.append(callback_name)

        return names

    def _suppress_root_fields(self) -> set[str]:
        if self.class_name in _FRAMEWORK_ROOT_SUPERCLASSES or _inherits_from(
            self.class_name, self.class_superclasses, _FRAMEWORK_ROOT_SUPERCLASSES
        ):
            return {"actor", "box", "menu"}

        return set()

    def _check_lifecycle(self, state: _ClassState) -> None:
        created = collect_resources_from_methods(
            self.text,
            self.ctx.path,
            state.enable_methods,
            self.ctx.mapper,
            self.destroyable_classes,
            set(),
            state.signal_manager_fields,
        )
        cleaned = collect_cleanup_from_methods(
            self.text,
            state.disable_methods,
            set(),
            set(created.signal_groups) | state.signal_manager_fields,
        )

        append_lifecycle_findings(
            self.ctx.findings,
            created,
            cleaned,
            include_object_cleanup=self.class_name not in self.destroyable_classes,
            release_container_names=set(),
            suppress_root_fields=self._suppress_root_fields(),
        )

    def _check_soup(self, state: _ClassState) -> None:
        _check_soup_abort(
            self.text, state.enable_methods, state.disable_methods, self.ctx
        )


# ---------------------------------------------------------------------------
# Rule
# ---------------------------------------------------------------------------


class LifecycleRule(FileRule):
    """
    FileRule: lifecycle analysis for entrypoint and non-entrypoint classes.

    Covers EGO_L_001 (pre-enable resources), EGO_L_002–EGO_L_005 (lifecycle
    cleanup), EGO_L_007 (runtime anonymous sources), EGO_L_008 (Soup.Session abort).
    """

    def check(self, root: Node, text: str, ctx: CheckContext) -> None:
        _EntrypointAnalyzer(text, root, ctx).run()
