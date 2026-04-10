# SPDX-License-Identifier: AGPL-3.0-or-later

"""Shared rule-facing constants loaded from the versioned API TOML."""

from __future__ import annotations

import tomllib
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "api.toml"

with _DATA_PATH.open("rb") as fp:
    _DATA = tomllib.load(fp)

_IMPORTS = _DATA["imports"]
_SUBPROCESS = _DATA["subprocess"]
_API_MISUSE = _DATA["api_misuse"]
_COMPAT = _DATA["compat"]

DEPRECATED_IMPORT_TOKENS = tuple(_IMPORTS["deprecated_modules"])
SHELL_FORBIDDEN_TOKENS = frozenset(_IMPORTS["shell_forbidden_libs"])
PREFS_FORBIDDEN_TOKENS = frozenset(_IMPORTS["prefs_forbidden_libs"])
SYNC_FILE_IO_CALL_NAMES = frozenset(_SUBPROCESS["sync_file_io_calls"])
EXTENSION_LOOKUP_CALL_NAMES = frozenset(_API_MISUSE["extension_lookup_calls"])
SPAWN_CALL_NAMES = frozenset(_SUBPROCESS["spawn_calls"])
NON_PKEXEC_PRIVILEGE_COMMANDS = frozenset(_SUBPROCESS["privilege_commands"])
SHELL_SYNC_SPAWN_CALL_NAMES = frozenset(_SUBPROCESS["sync_spawn_calls"])
GNOME49_SIGNAL_REMOVED_CLASSES = frozenset(
    _COMPAT["gnome49"]["removed_clutter_classes"]
)
GNOME50_REMOVED_DISPLAY_SIGNALS = frozenset(
    _COMPAT["gnome50"]["removed_display_signals"]
)

__all__ = [
    "DEPRECATED_IMPORT_TOKENS",
    "EXTENSION_LOOKUP_CALL_NAMES",
    "GNOME49_SIGNAL_REMOVED_CLASSES",
    "GNOME50_REMOVED_DISPLAY_SIGNALS",
    "NON_PKEXEC_PRIVILEGE_COMMANDS",
    "PREFS_FORBIDDEN_TOKENS",
    "SHELL_FORBIDDEN_TOKENS",
    "SHELL_SYNC_SPAWN_CALL_NAMES",
    "SPAWN_CALL_NAMES",
    "SYNC_FILE_IO_CALL_NAMES",
]
