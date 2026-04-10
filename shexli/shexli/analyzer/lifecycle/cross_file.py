# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Cross-file lifecycle analysis helpers (Phase 6).

Builds an index of imported helper functions that receive ``this`` as their
first parameter and assigns signals/sources back onto it.  The index is then
used by :func:`collect_resources_from_methods` and
:func:`collect_cleanup_from_methods` to extend resource and cleanup tracking
across file boundaries.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from tree_sitter import Node

from ...ast import (
    call_arguments,
    call_callee_parts,
    identifier_name,
    iter_nodes,
    member_expression_parts,
    parse_js,
    top_level_function_methods,
)
from ..engine import PathMapper
from ..evidence import node_evidence
from .base import (
    SOURCE_ADD_NAMES,
    SOURCE_REMOVE_NAMES,
    ResourceTracker,
    is_release_value,
    is_signal_connect_call,
    record_resource,
    resource_from_node,
)


class CrossFileEntry(NamedTuple):
    """A helper function that can be called as ``fn(this)``."""

    source: str  # full text of the helper file
    body: Node  # AST body node of the function
    param: str  # name of the first (this-proxy) parameter
    path: Path  # path to the helper file (for evidence)


if TYPE_CHECKING:
    from .types import CrossFileIndex


def _local_import_names(
    extension_source: str, extension_root: Node
) -> dict[str, tuple[str, str]]:
    """Return ``{local_name: (exported_name, module_path)}`` for relative imports.

    For ``import { connectAll as start } from './mod.js'`` the local name is
    ``start`` and the exported name is ``connectAll``.  For an un-aliased
    import both names are the same.  The index is keyed by the *local* name so
    call-site matching works even when imports are aliased.
    """
    result: dict[str, tuple[str, str]] = {}
    for child in extension_root.children:
        if child.type != "import_statement":
            continue
        module_node = None
        for sub in child.children:
            if sub.type == "string":
                module_node = sub
        if module_node is None:
            continue
        module = (
            extension_source.encode("utf-8")[
                module_node.start_byte : module_node.end_byte
            ]
            .decode("utf-8")
            .strip("\"'")
        )
        if not module.startswith("./"):
            continue
        for sub in child.children:
            if sub.type != "import_clause":
                continue
            for clause_child in sub.children:
                if clause_child.type == "named_imports":
                    for specifier in clause_child.children:
                        if specifier.type == "import_specifier":
                            exported_node = specifier.child_by_field_name("name")
                            alias_node = specifier.child_by_field_name("alias")
                            local_node = (
                                alias_node if alias_node is not None else exported_node
                            )
                            if exported_node is not None and local_node is not None:
                                exported = identifier_name(
                                    extension_source, exported_node
                                )
                                local = identifier_name(extension_source, local_node)
                                if exported and local:
                                    result[local] = (exported, module)
    return result


def build_cross_file_index(
    extension_source: str,
    extension_root: Node,
    pkg_dir: Path,
    parsed_helpers: dict[Path, tuple[str, Node]] | None = None,
) -> CrossFileIndex:
    """Return an index of imported helper functions usable as ``fn(this)``.

    The index is keyed by the **local** import name so call-site matching
    works even when imports are aliased (``import { foo as bar }``).
    """
    index: CrossFileIndex = {}
    local_names = _local_import_names(extension_source, extension_root)
    if not local_names:
        return index

    if parsed_helpers is None:
        parsed_helpers = {}

    for local_name, (exported_name, module) in local_names.items():
        rel = module[2:]  # strip "./"
        if not rel.endswith(".js"):
            rel = rel + ".js" if "." not in rel.rsplit("/", 1)[-1] else rel
        helper_path = pkg_dir / rel
        if not helper_path.is_file():
            continue

        cache_key = helper_path.resolve()

        if cache_key not in parsed_helpers:
            try:
                helper_source = helper_path.read_text(encoding="utf-8")
            except OSError:
                continue
            helper_tree = parse_js(helper_source)
            parsed_helpers[cache_key] = (helper_source, helper_tree.root_node)

        helper_source, helper_root = parsed_helpers[cache_key]
        helper_functions = top_level_function_methods(helper_source, helper_root)

        # Also find `export function name(...)` (export_statement wrapping
        # function_declaration).  Look up by exported_name, not local_name.
        if exported_name not in helper_functions:
            for child in helper_root.children:
                if child.type != "export_statement":
                    continue
                for sub in child.children:
                    if sub.type != "function_declaration":
                        continue
                    name_node = sub.child_by_field_name("name")
                    if name_node is None:
                        continue
                    name_text = helper_source.encode("utf-8")[
                        name_node.start_byte : name_node.end_byte
                    ].decode("utf-8")
                    if name_text == exported_name:
                        helper_functions.setdefault(exported_name, []).append(sub)

        if exported_name not in helper_functions:
            continue
        for fn_node in helper_functions[exported_name]:
            params = fn_node.child_by_field_name("parameters")
            body = fn_node.child_by_field_name("body")
            if params is None or body is None:
                continue
            if not params.named_children:
                continue
            first_param = identifier_name(helper_source, params.named_children[0])
            if first_param:
                # Key by local_name so the call site `local_name(this)` matches.
                index[local_name] = CrossFileEntry(
                    source=helper_source,
                    body=body,
                    param=first_param,
                    path=helper_path,
                )
                break

    return index


def build_cross_file_indices_per_file(
    js_files: list[Path],
) -> dict[Path, CrossFileIndex]:
    """Return a per-file cross-file index, keyed by the calling JS file's path.

    Each file gets its own index built from its own imports, so helpers with
    the same local name imported from different modules in different files do
    not overwrite each other.  Helper files are parsed once via a shared cache.
    """
    result: dict[Path, CrossFileIndex] = {}
    parsed_helpers: dict[Path, tuple[str, Node]] = {}
    for js_file in js_files:
        try:
            source = js_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        tree = parse_js(source)
        file_index = build_cross_file_index(
            source, tree.root_node, js_file.parent, parsed_helpers
        )
        if file_index:
            result[js_file] = file_index
    return result


# ---------------------------------------------------------------------------
# Targeted resource collection for cross-file bodies
# ---------------------------------------------------------------------------


def collect_cross_file_resources(
    tracker: ResourceTracker,
    index: CrossFileIndex,
    extension_source: str,
    extension_methods: list[Node],
    mapper: PathMapper,
    destroyable_classes: set[str],
) -> None:
    """
    For each call ``fn(this)`` found in *extension_methods* where ``fn`` is in
    *index*, process the helper body and record signals/sources/objects
    assigned to the ``this``-proxy parameter.
    """
    for method in extension_methods:
        body = method.child_by_field_name("body")
        if body is None:
            continue
        for node in iter_nodes(body):
            if node.type != "call_expression":
                continue
            parts = call_callee_parts(extension_source, node)
            if len(parts) != 1 or parts[0] not in index:
                continue
            args = call_arguments(node)
            if not args or args[0].type != "this":
                continue

            entry = index[parts[0]]
            _scan_helper_resources(tracker, entry, mapper, destroyable_classes)


def _scan_helper_resources(
    tracker: ResourceTracker,
    entry: CrossFileEntry,
    mapper: PathMapper,
    destroyable_classes: set[str],
) -> None:
    this_proxy = entry.param
    for node in iter_nodes(entry.body):
        if node.type == "assignment_expression":
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if left is None or right is None:
                continue
            parts = member_expression_parts(entry.source, left)
            if len(parts) != 2 or parts[0] != this_proxy:
                continue
            field = parts[1]
            evidence = node_evidence(entry.path, entry.source, node, mapper)
            kind = resource_from_node(entry.source, right, {}, destroyable_classes)
            if kind == "signal":
                record_resource(tracker.signals, field, evidence)
            elif kind == "source":
                record_resource(tracker.sources, field, evidence)
            elif kind == "object":
                record_resource(tracker.objects, field, evidence)
            elif kind == "resource_ref":
                record_resource(tracker.resource_refs, field, evidence)
        elif node.type == "call_expression":
            # Bare call_expression source creation (not assigned to a field)
            if (
                ".".join(call_callee_parts(entry.source, node)) in SOURCE_ADD_NAMES
                and node.parent is not None
                and node.parent.type == "expression_statement"
            ):
                evidence = node_evidence(entry.path, entry.source, node, mapper)
                record_resource(
                    tracker.sources,
                    f"anonymous-source:{node.start_point.row + 1}",
                    evidence,
                )
            # Bare signal connect (not assigned to a field) directly on the proxy
            if (
                is_signal_connect_call(entry.source, node)
                and node.parent is not None
                and node.parent.type == "expression_statement"
            ):
                fn = node.child_by_field_name("function")
                if fn is not None:
                    obj = fn.child_by_field_name("object")
                    if obj is not None:
                        obj_parts = member_expression_parts(entry.source, obj)
                        if len(obj_parts) == 1 and obj_parts[0] == this_proxy:
                            continue  # this_proxy.connect(...) — skip, it's self-signal
                evidence = node_evidence(entry.path, entry.source, node, mapper)
                record_resource(
                    tracker.signals,
                    f"anonymous-signal:{node.start_point.row + 1}",
                    evidence,
                )


# ---------------------------------------------------------------------------
# Targeted cleanup collection for cross-file bodies
# ---------------------------------------------------------------------------


def collect_cross_file_cleanup(
    tracker: ResourceTracker,
    index: CrossFileIndex,
    extension_source: str,
    extension_methods: list[Node],
) -> None:
    """
    For each call ``fn(this)`` in *extension_methods* where ``fn`` is in *index*,
    process the helper body and record signals/sources released via the
    ``this``-proxy parameter.
    """
    for method in extension_methods:
        body = method.child_by_field_name("body")
        if body is None:
            continue
        for node in iter_nodes(body):
            if node.type != "call_expression":
                continue
            parts = call_callee_parts(extension_source, node)
            if len(parts) != 1 or parts[0] not in index:
                continue
            args = call_arguments(node)
            if not args or args[0].type != "this":
                continue

            entry = index[parts[0]]
            _scan_helper_cleanup(tracker, entry)


def _scan_helper_cleanup(tracker: ResourceTracker, entry: CrossFileEntry) -> None:
    this_proxy = entry.param
    for node in iter_nodes(entry.body):
        if node.type == "assignment_expression":
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if left is None or right is None:
                continue
            parts = member_expression_parts(entry.source, left)
            if len(parts) != 2 or parts[0] != this_proxy:
                continue
            field = parts[1]
            if is_release_value(entry.source, right):
                record_resource(tracker.released_refs, field)

        elif node.type == "call_expression":
            fn = node.child_by_field_name("function")
            if fn is None:
                continue
            call_name = ".".join(call_callee_parts(entry.source, node))
            args = call_arguments(node)

            # obj.disconnect(extension._field) or
            # obj.disconnect(extension._field, ...)
            if call_name.endswith(".disconnect") or call_name == "disconnect":
                for arg in args:
                    parts = member_expression_parts(entry.source, arg)
                    if len(parts) == 2 and parts[0] == this_proxy:
                        record_resource(tracker.signals, parts[1])

            # GLib.source_remove(extension._field)
            if call_name in SOURCE_REMOVE_NAMES:
                for arg in args:
                    parts = member_expression_parts(entry.source, arg)
                    if len(parts) == 2 and parts[0] == this_proxy:
                        record_resource(tracker.sources, parts[1])
