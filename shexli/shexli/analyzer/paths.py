# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

PathMode = Literal["cli", "embedded"]


@dataclass(slots=True)
class PathMapper:
    root: Path
    input_path: Path
    mode: PathMode
    is_zip: bool

    def display_path(self, path: Path) -> str:
        package_path = self.package_path(path)
        if self.mode == "embedded":
            return package_path

        if self.is_zip:
            return f"{self.input_path.resolve()}:{package_path}"

        return str(path.resolve())

    def package_path(self, path: Path) -> str:
        return str(path.relative_to(self.root))

    def display_root(self) -> str:
        if self.mode == "embedded":
            return "."

        return str(self.input_path.resolve())
