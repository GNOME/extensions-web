# SPDX-License-Identifier: AGPL-3.0-or-later

"""Typed access to the versioned GNOME API data in data/api.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

_DATA_DIR = Path(__file__).parent / "data"


@dataclass(frozen=True)
class _Imports:
    deprecated_modules: tuple[str, ...]
    shell_forbidden_libs: frozenset[str]
    prefs_forbidden_libs: frozenset[str]


@dataclass(frozen=True)
class _Subprocess:
    spawn_calls: frozenset[str]
    sync_spawn_calls: frozenset[str]
    sync_file_io_calls: frozenset[str]
    privilege_commands: frozenset[str]


@dataclass(frozen=True)
class _ApiMisuse:
    extension_lookup_calls: frozenset[str]


@dataclass(frozen=True)
class _Lifecycle:
    forbidden_new_prefixes: frozenset[str]
    destroyable_namespace_roots: frozenset[str]
    destroyable_superclass_names: frozenset[str]
    resource_ref_call_names: frozenset[str]
    resource_ref_new_names: frozenset[str]
    source_add_names: frozenset[str]
    source_remove_names: frozenset[str]
    signal_manager_new_names: frozenset[str]
    framework_root_superclasses: frozenset[str]


@dataclass(frozen=True)
class _Gnome49:
    removed_clutter_classes: frozenset[str]


@dataclass(frozen=True)
class _Gnome50:
    removed_display_signals: frozenset[str]


@dataclass(frozen=True)
class _Compat:
    gnome49: _Gnome49
    gnome50: _Gnome50


@dataclass(frozen=True)
class ApiData:
    spec_version: str
    imports: _Imports
    subprocess: _Subprocess
    api_misuse: _ApiMisuse
    lifecycle: _Lifecycle
    compat: _Compat


def _load() -> ApiData:
    with (_DATA_DIR / "api.toml").open("rb") as fp:
        data = tomllib.load(fp)

    i = data["imports"]
    s = data["subprocess"]
    a = data["api_misuse"]
    lc = data["lifecycle"]
    c = data["compat"]

    return ApiData(
        spec_version=data["spec_version"],
        imports=_Imports(
            deprecated_modules=tuple(i["deprecated_modules"]),
            shell_forbidden_libs=frozenset(i["shell_forbidden_libs"]),
            prefs_forbidden_libs=frozenset(i["prefs_forbidden_libs"]),
        ),
        subprocess=_Subprocess(
            spawn_calls=frozenset(s["spawn_calls"]),
            sync_spawn_calls=frozenset(s["sync_spawn_calls"]),
            sync_file_io_calls=frozenset(s["sync_file_io_calls"]),
            privilege_commands=frozenset(s["privilege_commands"]),
        ),
        api_misuse=_ApiMisuse(
            extension_lookup_calls=frozenset(a["extension_lookup_calls"]),
        ),
        lifecycle=_Lifecycle(
            forbidden_new_prefixes=frozenset(lc["forbidden_new_prefixes"]),
            destroyable_namespace_roots=frozenset(lc["destroyable_namespace_roots"]),
            destroyable_superclass_names=frozenset(lc["destroyable_superclass_names"]),
            resource_ref_call_names=frozenset(lc["resource_ref_call_names"]),
            resource_ref_new_names=frozenset(lc["resource_ref_new_names"]),
            source_add_names=frozenset(lc["source_add_names"]),
            source_remove_names=frozenset(lc["source_remove_names"]),
            signal_manager_new_names=frozenset(lc["signal_manager_new_names"]),
            framework_root_superclasses=frozenset(lc["framework_root_superclasses"]),
        ),
        compat=_Compat(
            gnome49=_Gnome49(
                removed_clutter_classes=frozenset(
                    c["gnome49"]["removed_clutter_classes"]
                ),
            ),
            gnome50=_Gnome50(
                removed_display_signals=frozenset(
                    c["gnome50"]["removed_display_signals"]
                ),
            ),
        ),
    )


API: ApiData = _load()
