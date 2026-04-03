# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import os
from pathlib import Path

from ..ast import (
    call_arguments,
    call_callee_parts,
    default_export_class_methods,
    imports_in_program,
    iter_nodes,
    legacy_entrypoint_methods,
    member_expression_parts,
    node_text,
    parse_js,
)
from ..models import AnalysisLimits
from .patterns import (
    StringPattern,
    const_patterns_in_program,
    evaluate_string_pattern,
    getter_patterns_in_program,
)
from .safety import read_text_with_limit
from .spawn import SPAWN_CALL_NAMES, extract_gjs_module_target

ENTRYPOINT_CONTEXTS = {
    "extension.js": "shell",
    "prefs.js": "prefs",
}
CURRENT_EXTENSION_ROOT = "<current-extension>"


def _candidate_import_paths(base_dir: Path, module: str) -> list[Path]:
    base_path = base_dir / module
    candidates = [base_path]

    if base_path.suffix not in {".js", ".mjs"}:
        candidates.append(base_path.with_suffix(".js"))
        candidates.append(base_path.with_suffix(".mjs"))

    candidates.append(base_path / "index.js")
    candidates.append(base_path / "index.mjs")
    return candidates


def resolve_local_import(current_path: Path, module: str) -> Path | None:
    if not module.startswith("."):
        return None

    for candidate in _candidate_import_paths(current_path.parent, module):
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()

    return None


def _member_expression_parts_with_calls(
    source: str,
    node,
    current_extension_aliases: set[str],
) -> list[str]:
    if node.type == "member_expression":
        if not _contains_call_expression(node):
            parts = member_expression_parts(source, node)
            if parts:
                if parts[0] in current_extension_aliases:
                    parts[0] = CURRENT_EXTENSION_ROOT
                return parts

        object_node = node.child_by_field_name("object")
        property_node = node.child_by_field_name("property")
        if object_node is None or property_node is None:
            return []

        return _member_expression_parts_with_calls(
            source,
            object_node,
            current_extension_aliases,
        ) + _member_expression_parts_with_calls(
            source,
            property_node,
            current_extension_aliases,
        )

    if node.type == "call_expression":
        call_name = ".".join(call_callee_parts(source, node))
        if (
            call_name.endswith(".getCurrentExtension")
            or call_name == "getCurrentExtension"
        ):
            return [CURRENT_EXTENSION_ROOT]

        return []

    parts = member_expression_parts(source, node)
    if len(parts) == 1 and parts[0] in current_extension_aliases:
        return [CURRENT_EXTENSION_ROOT]

    return parts


def _contains_call_expression(node) -> bool:
    if node.type == "call_expression":
        return True

    if node.type != "member_expression":
        return False

    object_node = node.child_by_field_name("object")
    property_node = node.child_by_field_name("property")
    if object_node is None or property_node is None:
        return False

    return _contains_call_expression(object_node) or _contains_call_expression(
        property_node
    )


def _current_extension_aliases_in_program(source: str, root) -> set[str]:
    aliases: set[str] = set()

    for node in iter_nodes(root):
        if node.type != "variable_declarator":
            continue

        name_node = node.child_by_field_name("name")
        value_node = node.child_by_field_name("value")
        if (
            name_node is None
            or value_node is None
            or value_node.type != "call_expression"
        ):
            continue

        call_name = ".".join(call_callee_parts(source, value_node))
        if (
            call_name.endswith(".getCurrentExtension")
            or call_name == "getCurrentExtension"
        ):
            aliases.add(node_text(source, name_node))

    return aliases


def _resolve_gjs_module_target(
    root: Path,
    current_path: Path,
    target: str,
    js_file_set: set[Path],
) -> Path | None:
    imported_path = resolve_local_import(current_path, target)
    if imported_path is not None and imported_path in js_file_set:
        return imported_path

    root_candidate = (root / target).resolve()
    if root_candidate in js_file_set:
        return root_candidate

    if "${" not in target or not target.endswith(".js"):
        return None

    suffix = target.split("}/", 1)[-1].lstrip("/")
    if not suffix:
        return None

    matches = [
        path for path in js_file_set if str(path.relative_to(root)).endswith(suffix)
    ]
    if len(matches) == 1:
        return matches[0]

    return None


def legacy_local_imports_in_program(
    source: str,
    root,
    package_root: Path,
    js_file_set: set[Path],
) -> list[Path]:
    current_extension_aliases = _current_extension_aliases_in_program(source, root)
    imported_paths: list[Path] = []

    for node in iter_nodes(root):
        if node.type != "member_expression":
            continue

        parts = _member_expression_parts_with_calls(
            source,
            node,
            current_extension_aliases,
        )
        if (
            len(parts) < 3
            or parts[0] != CURRENT_EXTENSION_ROOT
            or parts[1] != "imports"
        ):
            continue

        import_parts = parts[2:]

        for length in range(len(import_parts), 0, -1):
            candidate = (package_root / Path(*import_parts[:length])).with_suffix(".js")
            candidate = candidate.resolve()
            if candidate in js_file_set:
                imported_paths.append(candidate)
                break

    return imported_paths


def _candidate_import_strings(current_path: Path, path: Path) -> set[str]:
    relative = os.path.relpath(path, current_path.parent).replace(os.sep, "/")
    candidates = {relative}
    if not relative.startswith("."):
        candidates.add(f"./{relative}")

    return candidates


def _resolve_dynamic_import_pattern(
    current_path: Path,
    pattern: StringPattern,
    js_file_set: set[Path],
) -> list[Path]:
    exact = pattern.exact
    if exact is not None:
        imported_path = resolve_local_import(current_path, exact)
        return (
            [imported_path]
            if imported_path is not None and imported_path in js_file_set
            else []
        )

    if not pattern.prefix and not pattern.suffix:
        return []

    if pattern.prefix.endswith("/"):
        base_dir = (current_path.parent / pattern.prefix).resolve()
        matches: list[Path] = []

        for candidate in js_file_set:
            try:
                relative = candidate.relative_to(base_dir)
            except ValueError:
                continue

            relative_string = relative.as_posix()
            if pattern.suffix and not relative_string.endswith(pattern.suffix):
                continue

            matches.append(candidate)

        return matches

    matches: list[Path] = []
    for candidate in js_file_set:
        import_strings = _candidate_import_strings(current_path, candidate)
        if any(
            value.startswith(pattern.prefix) and value.endswith(pattern.suffix)
            for value in import_strings
        ):
            matches.append(candidate)

    return matches


def dynamic_import_targets_in_program(
    source: str,
    root,
    current_path: Path,
    js_file_set: set[Path],
    const_patterns: dict[str, StringPattern],
    getter_patterns: dict[str, StringPattern],
) -> list[Path]:
    targets: list[Path] = []

    for node in iter_nodes(root):
        if node.type != "call_expression":
            continue

        function_node = node.child_by_field_name("function")
        if function_node is None or function_node.type != "import":
            continue

        arguments = call_arguments(node)
        if len(arguments) != 1:
            continue

        pattern = evaluate_string_pattern(
            source,
            arguments[0],
            const_patterns,
            getter_patterns,
        )
        if pattern is None:
            continue

        targets.extend(
            _resolve_dynamic_import_pattern(current_path, pattern, js_file_set)
        )

    return targets


def launched_local_modules_in_program(
    source: str,
    root,
    current_path: Path,
    package_root: Path,
    js_file_set: set[Path],
) -> list[Path]:
    launched: list[Path] = []

    for node in iter_nodes(root):
        if node.type != "call_expression":
            continue

        call_name = ".".join(call_callee_parts(source, node))
        if call_name not in SPAWN_CALL_NAMES:
            continue

        target = extract_gjs_module_target(source, node)
        if target is None:
            continue

        launched_path = _resolve_gjs_module_target(
            package_root,
            current_path,
            target,
            js_file_set,
        )
        if launched_path is None:
            continue

        launched.append(launched_path)

    return launched


def reachable_js_contexts(
    root: Path,
    js_files: list[Path],
    limits: AnalysisLimits,
) -> dict[Path, set[str]]:
    root = root.resolve()
    js_files = [path.resolve() for path in js_files]
    js_file_set = set(js_files)
    contexts: dict[Path, set[str]] = {}
    pending: list[tuple[Path, str]] = []
    seen: set[tuple[Path, str]] = set()

    for path in js_files:
        context = ENTRYPOINT_CONTEXTS.get(path.name)
        if context and path.parent == root:
            pending.append((path, context))

    while pending:
        path, context = pending.pop()
        key = (path, context)
        if key in seen:
            continue

        seen.add(key)
        contexts.setdefault(path, set()).add(context)

        try:
            text = read_text_with_limit(path, limits, encoding="utf-8")
        except UnicodeDecodeError:
            continue

        root_node = parse_js(text).root_node
        methods = default_export_class_methods(
            text, root_node
        ) or legacy_entrypoint_methods(
            text,
            root_node,
        )
        const_patterns = const_patterns_in_program(text, root_node, {})
        getter_patterns = getter_patterns_in_program(
            text,
            methods,
            const_patterns,
        )
        const_patterns = const_patterns_in_program(text, root_node, getter_patterns)

        for item in imports_in_program(text, root_node):
            if item.module is None:
                continue

            imported_path = resolve_local_import(path, item.module)
            if imported_path is None or imported_path not in js_file_set:
                continue

            pending.append((imported_path, context))

        for launched_path in launched_local_modules_in_program(
            text,
            root_node,
            path,
            root,
            js_file_set,
        ):
            pending.append((launched_path, "script"))

        for imported_path in legacy_local_imports_in_program(
            text,
            root_node,
            root,
            js_file_set,
        ):
            pending.append((imported_path, context))

        for imported_path in dynamic_import_targets_in_program(
            text,
            root_node,
            path,
            js_file_set,
            const_patterns,
            getter_patterns,
        ):
            pending.append((imported_path, context))

    return contexts
