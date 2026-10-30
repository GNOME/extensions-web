# SPDX-License-Identifier: AGPL-3.0-or-later

"""Two public rule families: JSFileRule and ExtensionRule.

Architectural invariants:
- JSFileRule receives JSFileFacts + JSFileCheckContext only. It does not see
  extension metadata, schemas, or cross-file structure.
- ExtensionRule receives ExtensionFacts + ExtensionCheckContext only. It does
  not see JSFileModel or iterate over files directly.
- Facts aggregate upward through builders only. ExtensionFactBuilder may call
  get_file_fact(); ExtensionRule may not.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from ..models import AnalysisLimits

if TYPE_CHECKING:
    from .file import JSFileModel
    from .lifecycle.types import CrossFileIndex
    from .metadata import Metadata
    from .rules.api import JSContext

PathMode = Literal["cli", "embedded"]


class JSContext(StrEnum):
    """Reachability-derived runtime context for an analyzed JS file."""

    EXTENSION = "extension"
    PREFERENCES = "preferences"
    SCRIPT = "script"


@dataclass(slots=True)
class PathMapper:
    """Runtime path formatter used for package and evidence display paths."""

    root: Path
    input_path: Path
    mode: PathMode
    is_zip: bool

    def display_path(self, path: Path) -> str:
        """Return the user-facing display path for one filesystem path."""
        package_path = self.package_path(path)
        if self.mode == "embedded":
            return package_path

        input_path = (
            self.input_path
            if not self.input_path.is_absolute()
            else self.input_path.resolve()
        )
        if self.is_zip:
            return f"{input_path}:{package_path}"

        return str(input_path / package_path)

    def package_path(self, path: Path) -> str:
        """Return the exact relative package path for one filesystem path."""
        return str(path.relative_to(self.root))

    def display_root(self) -> str:
        """Return the user-facing display root for the current analysis."""
        if self.mode == "embedded":
            return "."

        if self.input_path.is_absolute():
            return str(self.input_path.resolve())
        return str(self.input_path)


@dataclass(slots=True)
class PackageFile:
    """General package-file metadata exposed on :class:`ExtensionModel`.

    Attributes:
        path: Absolute path of the package file.
        package_path: Display/package-relative path used in findings.
        suffix: Lower-cased filename suffix.
        is_executable: Whether the regular file has the executable user bit.
    """

    path: Path
    package_path: str
    suffix: str
    is_executable: bool


@dataclass(slots=True)
class ExtensionModel:
    """Extension-level model available to :class:`ExtensionRule`.

    Attributes:
        cross_file_index: Per-file helper index used by lifecycle analysis.
            The key is the analyzed JS file path and the value is the
            cross-file helper index for that file.
        root_dir: Absolute path to the analyzed extension root.
        metadata: Parsed metadata object for ``metadata.json``.
        target_versions: Declared GNOME Shell major versions from metadata.
        js_file_count: Number of analyzed JS entry/reachable files.
        entrypoint_contexts: Reachability-derived contexts per analyzed file, e.g.
            ``{extension_js: {JSContext.EXTENSION}, prefs_js:
            {JSContext.PREFERENCES}}``.
            ExtensionRule should read this instead of inspecting files directly.
        unreachable_js_files: JS/MJS files in the package that are not
            reachable from ``extension.js`` or ``prefs.js`` imports.
        package_files: All regular package files as general model data.
        all_files: All regular files in the extension package.
            Available for artifact/schema fact builders. ExtensionRule must not
            access this field directly.
        js_files: JS/MJS files in the extension package (subset of all_files).
            Available for artifact fact builders. ExtensionRule must not access
            this field directly.
        limits: Analysis limits used for safe file reading in builders.
        mapper: Path formatter shared with fact builders for evidence generation.
        files: All analyzed JS file models keyed by absolute path.
            Internal support data for fact builders. ExtensionRule must not
            access this field directly.
        EXTENSION_ENTRYPOINT_PACKAGE_PATH: Known relative package path for the
            extension entrypoint source file.
        PREFERENCES_ENTRYPOINT_PACKAGE_PATH: Known relative package path for the
            preferences entrypoint source file.
        METADATA_PACKAGE_PATH: Known relative package path for the metadata
            file.
    """

    EXTENSION_ENTRYPOINT_PACKAGE_PATH = "extension.js"
    PREFERENCES_ENTRYPOINT_PACKAGE_PATH = "prefs.js"
    METADATA_PACKAGE_PATH = "metadata.json"

    cross_file_index: dict[Path, CrossFileIndex]
    root_dir: Path
    metadata: Metadata
    target_versions: set[int]
    js_file_count: int
    entrypoint_contexts: dict[Path, set[JSContext]]
    unreachable_js_files: list[Path]
    package_files: list[PackageFile]
    all_files: list[Path]
    js_files: list[Path]
    limits: AnalysisLimits
    mapper: PathMapper
    files: dict[Path, JSFileModel]

    def package_file(self, package_path: str) -> PackageFile | None:
        """Return the package file with exact relative package path, if present."""
        for package_file in self.package_files:
            if package_file.package_path == package_path:
                return package_file
        return None
