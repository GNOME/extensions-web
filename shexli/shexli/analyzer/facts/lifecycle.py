# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

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
from ..engine import PathMapper
from ..evidence import node_evidence as _node_evidence
from ..lifecycle.base import (
    JS_BUILTIN_CONTAINERS,
    SOURCE_ADD_NAMES,
    ResourceTracker,
    collect_destroyable_class_names,
    method_reachability,
)
from ..lifecycle.collect import (
    collect_cleanup_from_methods,
    collect_resources_from_methods,
    collect_signal_manager_fields,
)
from ..lifecycle.types import CrossFileIndex
from ..reachability import ENTRYPOINT_CONTEXTS
from .base import ExtensionFactBuilder, ExtensionFactContext

if TYPE_CHECKING:
    from ..engine import ExtensionModel

_FRAMEWORK_ROOT_SUPERCLASSES = API.lifecycle.framework_root_superclasses


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


def _local_class_refs(
    text: str,
    methods: list,
    local_class_names: set[str],
    path: Path,
    mapper: PathMapper,
) -> dict[str, Evidence]:
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

            refs.setdefault(left_parts[1], _node_evidence(path, text, node, mapper))

    return refs


def _constructor_custom_refs(
    text: str,
    methods: list,
    local_class_names: set[str],
    cleanup_touched_fields: set[str],
    path: Path,
    mapper: PathMapper,
) -> dict[str, Evidence]:
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

            refs.setdefault(field_name, _node_evidence(path, text, node, mapper))

    return refs


def _runtime_anonymous_sources(
    text: str,
    methods: dict[str, list],
    path: Path,
    mapper: PathMapper,
) -> dict[str, Evidence]:
    cleanup_names = {"disable", "destroy", "_destroy", "dispose", "cleanup", "stop"}
    sources: dict[str, Evidence] = {}

    for method_name, method_nodes in methods.items():
        if method_name in cleanup_names:
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
                sources.setdefault(key, _node_evidence(path, text, node, mapper))

    return sources


@dataclass(slots=True)
class _LifecycleScopeInventory:
    created: ResourceTracker
    cleaned: ResourceTracker
    include_object_cleanup: bool = True
    release_container_names: set[str] = field(default_factory=set)
    suppress_root_fields: set[str] = field(default_factory=set)
    soup_session_evidences: dict[str, Evidence] = field(default_factory=dict)
    aborted_soup_sessions: set[str] = field(default_factory=set)


@dataclass(slots=True)
class _FileLifecycleInventory:
    pre_enable_evidences: list[Evidence]
    scopes: list[_LifecycleScopeInventory]


@dataclass(slots=True)
class _LifecycleInventoryFact:
    by_path: dict[Path, _FileLifecycleInventory]


@dataclass(slots=True, frozen=True)
class PreEnableObservation:
    """Observed code that runs before `enable()` and has evidence.

    Attributes:
        evidence: Evidence for work that happens before `enable()`.
    """

    evidence: Evidence


@dataclass(slots=True)
class PreEnableObservationFact:
    """Pre-enable observations grouped by analyzed file.

    Attributes:
        by_path: Observations keyed by analyzed file path.
    """

    by_path: dict[Path, list[PreEnableObservation]]


@dataclass(slots=True)
class SignalConnectObservation:
    """Observed signal connections for one lifecycle scope.

    Attributes:
        scope_id: Stable per-file scope identifier.
        signals: Individually connected signals by resource key.
        signal_groups: Grouped signal-manager style connections by resource key.
        parent_owned: Resources implicitly owned by a parent container.
        local_parent_owned: Scope-local parent-owned resources.
        menu_owned: Menu-owned resource keys.
        suppress_root_fields: Root fields to ignore in matching logic.
    """

    scope_id: int
    signals: dict[str, Evidence | None]
    signal_groups: dict[str, Evidence | None]
    parent_owned: dict[str, str]
    local_parent_owned: dict[str, str]
    menu_owned: set[str]
    suppress_root_fields: set[str]


@dataclass(slots=True)
class SignalDisconnectObservation:
    """Observed signal disconnections for one lifecycle scope.

    Attributes:
        scope_id: Stable per-file scope identifier.
        signals: Individually disconnected signals by resource key.
        signal_groups: Grouped signal-manager style disconnections by key.
    """

    scope_id: int
    signals: dict[str, Evidence | None]
    signal_groups: dict[str, Evidence | None]


@dataclass(slots=True)
class SignalConnectFact:
    """Signal connect observations grouped by analyzed file.

    Attributes:
        by_path: Connect observations keyed by analyzed file path.
    """

    by_path: dict[Path, list[SignalConnectObservation]]


@dataclass(slots=True)
class SignalDisconnectFact:
    """Signal disconnect observations grouped by analyzed file.

    Attributes:
        by_path: Disconnect observations keyed by analyzed file path.
    """

    by_path: dict[Path, list[SignalDisconnectObservation]]


@dataclass(slots=True)
class SourceAddObservation:
    """Observed GLib source additions for one lifecycle scope.

    Attributes:
        scope_id: Stable per-file scope identifier.
        sources: Individually added sources by resource key.
        source_groups: Grouped source additions by resource key.
    """

    scope_id: int
    sources: dict[str, Evidence | None]
    source_groups: dict[str, Evidence | None]


@dataclass(slots=True)
class SourceRemoveObservation:
    """Observed GLib source removals for one lifecycle scope.

    Attributes:
        scope_id: Stable per-file scope identifier.
        sources: Individually removed sources by resource key.
        source_groups: Grouped source removals by resource key.
    """

    scope_id: int
    sources: dict[str, Evidence | None]
    source_groups: dict[str, Evidence | None]


@dataclass(slots=True)
class SourceRecreateObservation:
    """Observed recreated GLib sources for one lifecycle scope.

    Attributes:
        scope_id: Stable per-file scope identifier.
        recreated_sources: Recreated source keys and their evidence.
    """

    scope_id: int
    recreated_sources: dict[str, Evidence | None]


@dataclass(slots=True)
class SourceAddFact:
    """Source-add observations grouped by analyzed file.

    Attributes:
        by_path: Source-add observations keyed by analyzed file path.
    """

    by_path: dict[Path, list[SourceAddObservation]]


@dataclass(slots=True)
class SourceRemoveFact:
    """Source-remove observations grouped by analyzed file.

    Attributes:
        by_path: Source-remove observations keyed by analyzed file path.
    """

    by_path: dict[Path, list[SourceRemoveObservation]]


@dataclass(slots=True)
class SourceRecreateFact:
    """Source-recreate observations grouped by analyzed file.

    Attributes:
        by_path: Source-recreate observations keyed by analyzed file path.
    """

    by_path: dict[Path, list[SourceRecreateObservation]]


@dataclass(slots=True)
class ObjectCreateObservation:
    """Observed object creation for one lifecycle scope.

    Attributes:
        scope_id: Stable per-file scope identifier.
        objects: Individually created objects by resource key.
        object_groups: Grouped object creations by resource key.
        parent_owned: Resources implicitly owned by a parent container.
        local_parent_owned: Scope-local parent-owned resources.
        suppress_root_fields: Root fields to ignore in matching logic.
        include_object_cleanup: Whether object cleanup is expected for the
            scope.
    """

    scope_id: int
    objects: dict[str, Evidence | None]
    object_groups: dict[str, Evidence | None]
    parent_owned: dict[str, str]
    local_parent_owned: dict[str, str]
    suppress_root_fields: set[str]
    include_object_cleanup: bool


@dataclass(slots=True)
class ObjectDestroyObservation:
    """Observed object destruction for one lifecycle scope.

    Attributes:
        scope_id: Stable per-file scope identifier.
        objects: Individually destroyed objects by resource key.
        object_groups: Grouped object destruction by resource key.
    """

    scope_id: int
    objects: dict[str, Evidence | None]
    object_groups: dict[str, Evidence | None]


@dataclass(slots=True)
class RefAssignObservation:
    """Observed reference retention for one lifecycle scope.

    Attributes:
        scope_id: Stable per-file scope identifier.
        resource_refs: Retained resource references by key.
        containers: Containers used to retain resources by key.
        parent_owned: Resources implicitly owned by a parent container.
        local_parent_owned: Scope-local parent-owned resources.
        release_container_names: Containers expected to be released later.
        include_object_cleanup: Whether object cleanup is expected for the
            scope.
    """

    scope_id: int
    resource_refs: dict[str, Evidence | None]
    containers: dict[str, Evidence | None]
    parent_owned: dict[str, str]
    local_parent_owned: dict[str, str]
    release_container_names: set[str]
    include_object_cleanup: bool


@dataclass(slots=True)
class RefReleaseObservation:
    """Observed reference releases for one lifecycle scope.

    Attributes:
        scope_id: Stable per-file scope identifier.
        released_refs: Released resource references by key.
    """

    scope_id: int
    released_refs: dict[str, Evidence | None]


@dataclass(slots=True)
class ObjectCreateFact:
    """Object-create observations grouped by analyzed file.

    Attributes:
        by_path: Object-create observations keyed by analyzed file path.
    """

    by_path: dict[Path, list[ObjectCreateObservation]]


@dataclass(slots=True)
class ObjectDestroyFact:
    """Object-destroy observations grouped by analyzed file.

    Attributes:
        by_path: Object-destroy observations keyed by analyzed file path.
    """

    by_path: dict[Path, list[ObjectDestroyObservation]]


@dataclass(slots=True)
class RefAssignFact:
    """Reference-assignment observations grouped by analyzed file.

    Attributes:
        by_path: Reference-assignment observations keyed by analyzed file path.
    """

    by_path: dict[Path, list[RefAssignObservation]]


@dataclass(slots=True)
class RefReleaseFact:
    """Reference-release observations grouped by analyzed file.

    Attributes:
        by_path: Reference-release observations keyed by analyzed file path.
    """

    by_path: dict[Path, list[RefReleaseObservation]]


@dataclass(slots=True, frozen=True)
class SoupSessionCreateObservation:
    """Observed Soup session creation retained on a field.

    Attributes:
        scope_id: Stable per-file scope identifier.
        field_name: Field that stores the Soup session.
        evidence: Evidence pointing at the creation site.
    """

    scope_id: int
    field_name: str
    evidence: Evidence


@dataclass(slots=True, frozen=True)
class SoupSessionAbortObservation:
    """Observed Soup session abort for a retained field.

    Attributes:
        scope_id: Stable per-file scope identifier.
        field_name: Field whose Soup session is aborted.
    """

    scope_id: int
    field_name: str


@dataclass(slots=True)
class SoupSessionCreateFact:
    """Soup-session-create observations grouped by analyzed file.

    Attributes:
        by_path: Soup session creation observations keyed by file path.
    """

    by_path: dict[Path, list[SoupSessionCreateObservation]]


@dataclass(slots=True)
class SoupSessionAbortFact:
    """Soup-session-abort observations grouped by analyzed file.

    Attributes:
        by_path: Soup session abort observations keyed by file path.
    """

    by_path: dict[Path, list[SoupSessionAbortObservation]]


@dataclass(slots=True)
class _EntrypointState:
    methods: dict[str, list]
    module_vars: set[str]
    destroyable_classes: set[str]
    local_class_names: set[str]
    class_superclasses: dict[str, str]
    signal_manager_fields: set[str]
    cross_file_index: CrossFileIndex | None


class _LifecycleFactsBuilder:
    def __init__(self, extension_model: ExtensionModel, path: Path) -> None:
        self.extension_model = extension_model
        self.file_model = extension_model.files[path]
        self.state = self._build_state()
        self._reachability_cache: dict[tuple[str, ...], list] = {}

    def _collect_methods(self) -> dict[str, list]:
        text = self.file_model.text
        root = self.file_model.root
        if self.file_model.path.name not in ENTRYPOINT_CONTEXTS:
            return {}

        methods = default_export_class_methods(text, root) or legacy_entrypoint_methods(
            text, root
        )
        if not methods:
            return {}

        for name, nodes in top_level_function_methods(text, root).items():
            methods.setdefault(name, []).extend(nodes)

        return methods

    def _build_state(self) -> _EntrypointState:
        text = self.file_model.text
        root = self.file_model.root
        methods = self._collect_methods()
        module_vars = top_level_variable_names(text, root)
        destroyable_classes = collect_destroyable_class_names(text, root)

        ctor_enable = method_reachability(
            text, methods, ["constructor", "_init", "enable"]
        )
        signal_manager_fields = collect_signal_manager_fields(
            text, ctor_enable, destroyable_classes, module_vars
        )

        return _EntrypointState(
            methods=methods,
            module_vars=module_vars,
            destroyable_classes=destroyable_classes,
            local_class_names=top_level_class_names(text, root),
            class_superclasses=top_level_class_superclasses(text, root),
            signal_manager_fields=signal_manager_fields,
            cross_file_index=self.extension_model.cross_file_index.get(
                self.file_model.path
            ),
        )

    def _reachable(self, start_names: list[str]) -> list:
        key = tuple(start_names)
        if key not in self._reachability_cache:
            self._reachability_cache[key] = method_reachability(
                self.file_model.text, self.state.methods, start_names
            )
        return self._reachability_cache[key]

    def collect_pre_enable_evidences(self) -> list[Evidence]:
        text = self.file_model.text
        path = self.file_model.path
        mapper = self.file_model.mapper
        constructor_methods = self._reachable(["constructor", "_init"])
        cleanup = collect_cleanup_from_methods(
            text,
            self._reachable(["disable"]),
            self.state.module_vars,
            self.state.signal_manager_fields,
            cross_file_index=self.state.cross_file_index,
        )

        evidence = _collect_pre_enable_evidence(
            text, path, self.file_model.root, self.state.methods, mapper
        )
        evidence.extend(
            _constructor_custom_refs(
                text,
                constructor_methods,
                self.state.local_class_names,
                set(cleanup.touched_refs) | set(cleanup.released_refs),
                path,
                mapper,
            ).values()
        )
        return evidence

    def _collect_entrypoint_scope(self) -> _LifecycleScopeInventory:
        text = self.file_model.text
        path = self.file_model.path
        mapper = self.file_model.mapper
        enable_methods = self._reachable(["enable"])
        disable_methods = self._reachable(["disable"])
        constructor_methods = self._reachable(["constructor", "_init"])
        ctor_enable_methods = self._reachable(["constructor", "_init", "enable"])

        created = collect_resources_from_methods(
            text,
            path,
            enable_methods,
            mapper,
            self.state.destroyable_classes,
            self.state.module_vars,
            self.state.signal_manager_fields,
            cross_file_index=self.state.cross_file_index,
        )
        cleaned = collect_cleanup_from_methods(
            text,
            disable_methods,
            self.state.module_vars,
            set(created.signal_groups) | self.state.signal_manager_fields,
            cross_file_index=self.state.cross_file_index,
        )

        for name, evidence in collect_resources_from_methods(
            text,
            path,
            constructor_methods,
            mapper,
            self.state.destroyable_classes,
            self.state.module_vars,
        ).resource_refs.items():
            created.resource_refs.setdefault(name, evidence)

        for name, evidence in _local_class_refs(
            text, ctor_enable_methods, self.state.local_class_names, path, mapper
        ).items():
            created.resource_refs.setdefault(name, evidence)

        for name, evidence in _constructor_custom_refs(
            text,
            constructor_methods,
            self.state.local_class_names,
            set(cleaned.touched_refs) | set(cleaned.released_refs),
            path,
            mapper,
        ).items():
            created.resource_refs.setdefault(name, evidence)

        for name, evidence in _runtime_anonymous_sources(
            text, self.state.methods, path, mapper
        ).items():
            created.sources.setdefault(name, evidence)

        soup_evidences = {
            field_name: _node_evidence(path, text, nodes[0], mapper)
            for field_name, nodes in _soup_session_fields(
                text, ctor_enable_methods
            ).items()
        }

        return _LifecycleScopeInventory(
            created=created,
            cleaned=cleaned,
            release_container_names=self.state.module_vars,
            soup_session_evidences=soup_evidences,
            aborted_soup_sessions=_aborted_soup_session_fields(text, disable_methods),
        )

    def _collect_class_scope(
        self,
        class_name: str,
        class_methods: dict[str, list],
    ) -> _LifecycleScopeInventory | None:
        text = self.file_model.text
        path = self.file_model.path
        mapper = self.file_model.mapper
        enable_methods = method_reachability(
            text, class_methods, ["constructor", "_init", "enable"]
        )
        if not enable_methods:
            return None

        cleanup_names = ["disable", "destroy", "_destroy", "dispose", "cleanup", "stop"]
        for method in enable_methods:
            body = method.child_by_field_name("body")
            if body is None:
                continue
            for callback_name in connect_callback_methods_for_events(
                text, body, {"destroy"}
            ):
                if callback_name not in cleanup_names:
                    cleanup_names.append(callback_name)

        disable_methods = method_reachability(text, class_methods, cleanup_names)

        signal_manager_fields = collect_signal_manager_fields(
            text, enable_methods, self.state.destroyable_classes, set()
        )

        created = collect_resources_from_methods(
            text,
            path,
            enable_methods,
            mapper,
            self.state.destroyable_classes,
            set(),
            signal_manager_fields,
        )
        cleaned = collect_cleanup_from_methods(
            text,
            disable_methods,
            set(),
            set(created.signal_groups) | signal_manager_fields,
        )

        suppress_root_fields: set[str] = set()
        if class_name in _FRAMEWORK_ROOT_SUPERCLASSES or _inherits_from(
            class_name, self.state.class_superclasses, _FRAMEWORK_ROOT_SUPERCLASSES
        ):
            suppress_root_fields = {"actor", "box", "menu"}

        soup_evidences = {
            field_name: _node_evidence(path, text, nodes[0], mapper)
            for field_name, nodes in _soup_session_fields(text, enable_methods).items()
        }

        return _LifecycleScopeInventory(
            created=created,
            cleaned=cleaned,
            include_object_cleanup=class_name not in self.state.destroyable_classes,
            suppress_root_fields=suppress_root_fields,
            soup_session_evidences=soup_evidences,
            aborted_soup_sessions=_aborted_soup_session_fields(text, disable_methods),
        )

    def _collect_scopes(self) -> list[_LifecycleScopeInventory]:
        text = self.file_model.text
        root = self.file_model.root
        scopes: list[_LifecycleScopeInventory] = []

        scopes.append(self._collect_entrypoint_scope())

        entrypoint_node_ids = {
            id(node)
            for method_nodes in self.state.methods.values()
            for node in method_nodes
        }

        for class_name, class_methods in top_level_class_methods(text, root).items():
            class_nodes = [
                node for method_nodes in class_methods.values() for node in method_nodes
            ]
            if class_nodes and all(
                id(node) in entrypoint_node_ids for node in class_nodes
            ):
                continue

            class_scope = self._collect_class_scope(class_name, class_methods)
            if class_scope is not None:
                scopes.append(class_scope)

        return scopes


def build_lifecycle_inventory(
    extension_model: ExtensionModel,
) -> _LifecycleInventoryFact:
    """Build reusable raw lifecycle inventory for all analyzed JS files."""
    by_path: dict[Path, _FileLifecycleInventory] = {}
    for path in sorted(extension_model.files):
        builder = _LifecycleFactsBuilder(extension_model, path)
        by_path[path] = _FileLifecycleInventory(
            pre_enable_evidences=builder.collect_pre_enable_evidences(),
            scopes=builder._collect_scopes(),
        )

    return _LifecycleInventoryFact(by_path=by_path)


def _collect_pre_enable_evidence(
    source: str,
    path: Path,
    root,
    methods: dict[str, list],
    mapper: PathMapper,
) -> list[Evidence]:
    from .lifecycle_preenable import collect_pre_enable_evidence

    return collect_pre_enable_evidence(source, path, root, methods, mapper)


class LifecycleInventoryFactBuilder(ExtensionFactBuilder[_LifecycleInventoryFact]):
    """Shared expensive lifecycle inventory reused by public lifecycle facts."""

    fact_type = _LifecycleInventoryFact

    def build(
        self,
        ctx: ExtensionFactContext,
    ) -> _LifecycleInventoryFact:
        return build_lifecycle_inventory(ctx.extension)


class PreEnableObservationFactBuilder(ExtensionFactBuilder[PreEnableObservationFact]):
    """Build pre-enable observations grouped by analyzed file."""

    fact_type = PreEnableObservationFact

    def build(self, ctx: ExtensionFactContext) -> PreEnableObservationFact:
        """Aggregate pre-enable observations from lifecycle inventory."""
        inventory = ctx.get_extension_fact(_LifecycleInventoryFact)
        by_path = {
            path: [
                PreEnableObservation(evidence=evidence)
                for evidence in file_inventory.pre_enable_evidences
            ]
            for path, file_inventory in inventory.by_path.items()
        }
        return PreEnableObservationFact(by_path=by_path)


class SignalConnectFactBuilder(ExtensionFactBuilder[SignalConnectFact]):
    """Build signal-connect observations grouped by analyzed file."""

    fact_type = SignalConnectFact

    def build(self, ctx: ExtensionFactContext) -> SignalConnectFact:
        """Aggregate signal-connect observations from lifecycle inventory."""
        inventory = ctx.get_extension_fact(_LifecycleInventoryFact)
        by_path: dict[Path, list[SignalConnectObservation]] = {}
        for path, file_inventory in inventory.by_path.items():
            by_path[path] = [
                SignalConnectObservation(
                    scope_id=index,
                    signals=dict(scope.created.signals),
                    signal_groups=dict(scope.created.signal_groups),
                    parent_owned=dict(scope.created.parent_owned),
                    local_parent_owned=dict(scope.created.local_parent_owned),
                    menu_owned=set(scope.created.menu_owned),
                    suppress_root_fields=set(scope.suppress_root_fields),
                )
                for index, scope in enumerate(file_inventory.scopes)
            ]
        return SignalConnectFact(by_path=by_path)


class SignalDisconnectFactBuilder(ExtensionFactBuilder[SignalDisconnectFact]):
    """Build signal-disconnect observations grouped by analyzed file."""

    fact_type = SignalDisconnectFact

    def build(self, ctx: ExtensionFactContext) -> SignalDisconnectFact:
        """Aggregate signal-disconnect observations from lifecycle inventory."""
        inventory = ctx.get_extension_fact(_LifecycleInventoryFact)
        by_path: dict[Path, list[SignalDisconnectObservation]] = {}
        for path, file_inventory in inventory.by_path.items():
            by_path[path] = [
                SignalDisconnectObservation(
                    scope_id=index,
                    signals=dict(scope.cleaned.signals),
                    signal_groups=dict(scope.cleaned.signal_groups),
                )
                for index, scope in enumerate(file_inventory.scopes)
            ]
        return SignalDisconnectFact(by_path=by_path)


class SourceAddFactBuilder(ExtensionFactBuilder[SourceAddFact]):
    """Build source-add observations grouped by analyzed file."""

    fact_type = SourceAddFact

    def build(self, ctx: ExtensionFactContext) -> SourceAddFact:
        """Aggregate source-add observations from lifecycle inventory."""
        inventory = ctx.get_extension_fact(_LifecycleInventoryFact)
        by_path: dict[Path, list[SourceAddObservation]] = {}
        for path, file_inventory in inventory.by_path.items():
            by_path[path] = [
                SourceAddObservation(
                    scope_id=index,
                    sources=dict(scope.created.sources),
                    source_groups=dict(scope.created.source_groups),
                )
                for index, scope in enumerate(file_inventory.scopes)
            ]
        return SourceAddFact(by_path=by_path)


class SourceRemoveFactBuilder(ExtensionFactBuilder[SourceRemoveFact]):
    """Build source-remove observations grouped by analyzed file."""

    fact_type = SourceRemoveFact

    def build(self, ctx: ExtensionFactContext) -> SourceRemoveFact:
        """Aggregate source-remove observations from lifecycle inventory."""
        inventory = ctx.get_extension_fact(_LifecycleInventoryFact)
        by_path: dict[Path, list[SourceRemoveObservation]] = {}
        for path, file_inventory in inventory.by_path.items():
            by_path[path] = [
                SourceRemoveObservation(
                    scope_id=index,
                    sources=dict(scope.cleaned.sources),
                    source_groups=dict(scope.cleaned.source_groups),
                )
                for index, scope in enumerate(file_inventory.scopes)
            ]
        return SourceRemoveFact(by_path=by_path)


class SourceRecreateFactBuilder(ExtensionFactBuilder[SourceRecreateFact]):
    """Build source-recreate observations grouped by analyzed file."""

    fact_type = SourceRecreateFact

    def build(self, ctx: ExtensionFactContext) -> SourceRecreateFact:
        """Aggregate source-recreate observations from lifecycle inventory."""
        inventory = ctx.get_extension_fact(_LifecycleInventoryFact)
        by_path: dict[Path, list[SourceRecreateObservation]] = {}
        for path, file_inventory in inventory.by_path.items():
            by_path[path] = [
                SourceRecreateObservation(
                    scope_id=index,
                    recreated_sources=dict(scope.created.recreated_sources),
                )
                for index, scope in enumerate(file_inventory.scopes)
            ]
        return SourceRecreateFact(by_path=by_path)


class ObjectCreateFactBuilder(ExtensionFactBuilder[ObjectCreateFact]):
    """Build object-create observations grouped by analyzed file."""

    fact_type = ObjectCreateFact

    def build(self, ctx: ExtensionFactContext) -> ObjectCreateFact:
        """Aggregate object-create observations from lifecycle inventory."""
        inventory = ctx.get_extension_fact(_LifecycleInventoryFact)
        by_path: dict[Path, list[ObjectCreateObservation]] = {}
        for path, file_inventory in inventory.by_path.items():
            by_path[path] = [
                ObjectCreateObservation(
                    scope_id=index,
                    objects=dict(scope.created.objects),
                    object_groups=dict(scope.created.object_groups),
                    parent_owned=dict(scope.created.parent_owned),
                    local_parent_owned=dict(scope.created.local_parent_owned),
                    suppress_root_fields=set(scope.suppress_root_fields),
                    include_object_cleanup=scope.include_object_cleanup,
                )
                for index, scope in enumerate(file_inventory.scopes)
            ]
        return ObjectCreateFact(by_path=by_path)


class ObjectDestroyFactBuilder(ExtensionFactBuilder[ObjectDestroyFact]):
    """Build object-destroy observations grouped by analyzed file."""

    fact_type = ObjectDestroyFact

    def build(self, ctx: ExtensionFactContext) -> ObjectDestroyFact:
        """Aggregate object-destroy observations from lifecycle inventory."""
        inventory = ctx.get_extension_fact(_LifecycleInventoryFact)
        by_path: dict[Path, list[ObjectDestroyObservation]] = {}
        for path, file_inventory in inventory.by_path.items():
            by_path[path] = [
                ObjectDestroyObservation(
                    scope_id=index,
                    objects=dict(scope.cleaned.objects),
                    object_groups=dict(scope.cleaned.object_groups),
                )
                for index, scope in enumerate(file_inventory.scopes)
            ]
        return ObjectDestroyFact(by_path=by_path)


class RefAssignFactBuilder(ExtensionFactBuilder[RefAssignFact]):
    """Build reference-assignment observations grouped by analyzed file."""

    fact_type = RefAssignFact

    def build(self, ctx: ExtensionFactContext) -> RefAssignFact:
        """Aggregate reference-assignment observations from lifecycle inventory."""
        inventory = ctx.get_extension_fact(_LifecycleInventoryFact)
        by_path: dict[Path, list[RefAssignObservation]] = {}
        for path, file_inventory in inventory.by_path.items():
            by_path[path] = [
                RefAssignObservation(
                    scope_id=index,
                    resource_refs=dict(scope.created.resource_refs),
                    containers=dict(scope.created.containers),
                    parent_owned=dict(scope.created.parent_owned),
                    local_parent_owned=dict(scope.created.local_parent_owned),
                    release_container_names=set(scope.release_container_names),
                    include_object_cleanup=scope.include_object_cleanup,
                )
                for index, scope in enumerate(file_inventory.scopes)
            ]
        return RefAssignFact(by_path=by_path)


class RefReleaseFactBuilder(ExtensionFactBuilder[RefReleaseFact]):
    """Build reference-release observations grouped by analyzed file."""

    fact_type = RefReleaseFact

    def build(self, ctx: ExtensionFactContext) -> RefReleaseFact:
        """Aggregate reference-release observations from lifecycle inventory."""
        inventory = ctx.get_extension_fact(_LifecycleInventoryFact)
        by_path: dict[Path, list[RefReleaseObservation]] = {}
        for path, file_inventory in inventory.by_path.items():
            by_path[path] = [
                RefReleaseObservation(
                    scope_id=index,
                    released_refs=dict(scope.cleaned.released_refs),
                )
                for index, scope in enumerate(file_inventory.scopes)
            ]
        return RefReleaseFact(by_path=by_path)


class SoupSessionCreateFactBuilder(ExtensionFactBuilder[SoupSessionCreateFact]):
    """Build Soup-session-create observations grouped by analyzed file."""

    fact_type = SoupSessionCreateFact

    def build(self, ctx: ExtensionFactContext) -> SoupSessionCreateFact:
        """Aggregate Soup-session-create observations from lifecycle inventory."""
        inventory = ctx.get_extension_fact(_LifecycleInventoryFact)
        by_path: dict[Path, list[SoupSessionCreateObservation]] = {}
        for path, file_inventory in inventory.by_path.items():
            observations: list[SoupSessionCreateObservation] = []
            for index, scope in enumerate(file_inventory.scopes):
                for field_name, evidence in scope.soup_session_evidences.items():
                    observations.append(
                        SoupSessionCreateObservation(
                            scope_id=index,
                            field_name=field_name,
                            evidence=evidence,
                        )
                    )
            by_path[path] = observations
        return SoupSessionCreateFact(by_path=by_path)


class SoupSessionAbortFactBuilder(ExtensionFactBuilder[SoupSessionAbortFact]):
    """Build Soup-session-abort observations grouped by analyzed file."""

    fact_type = SoupSessionAbortFact

    def build(self, ctx: ExtensionFactContext) -> SoupSessionAbortFact:
        """Aggregate Soup-session-abort observations from lifecycle inventory."""
        inventory = ctx.get_extension_fact(_LifecycleInventoryFact)
        by_path: dict[Path, list[SoupSessionAbortObservation]] = {}
        for path, file_inventory in inventory.by_path.items():
            observations: list[SoupSessionAbortObservation] = []
            for index, scope in enumerate(file_inventory.scopes):
                observations.extend(
                    SoupSessionAbortObservation(
                        scope_id=index,
                        field_name=field_name,
                    )
                    for field_name in sorted(scope.aborted_soup_sessions)
                )
            by_path[path] = observations
        return SoupSessionAbortFact(by_path=by_path)
