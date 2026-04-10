# SPDX-License-Identifier: AGPL-3.0-or-later

"""Shared rule-facing constants derived from the canonical API data."""

from __future__ import annotations

from ...api_data import API

DEPRECATED_IMPORT_TOKENS = API.imports.deprecated_modules
SHELL_FORBIDDEN_TOKENS = API.imports.shell_forbidden_libs
PREFS_FORBIDDEN_TOKENS = API.imports.prefs_forbidden_libs
SYNC_FILE_IO_CALL_NAMES = API.subprocess.sync_file_io_calls
EXTENSION_LOOKUP_CALL_NAMES = API.api_misuse.extension_lookup_calls
SPAWN_CALL_NAMES = API.subprocess.spawn_calls
NON_PKEXEC_PRIVILEGE_COMMANDS = API.subprocess.privilege_commands
SHELL_SYNC_SPAWN_CALL_NAMES = API.subprocess.sync_spawn_calls
GNOME49_SIGNAL_REMOVED_CLASSES = API.compat.gnome49.removed_clutter_classes
GNOME50_REMOVED_DISPLAY_SIGNALS = API.compat.gnome50.removed_display_signals

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
