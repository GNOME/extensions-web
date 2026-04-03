# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from pathlib import Path

from tree_sitter import Node

from ..ast import node_text
from ..models import Evidence
from .paths import PathMapper


def display_evidence(
    path: Path,
    mapper: PathMapper,
    *,
    line: int | None = None,
    snippet: str = "",
) -> Evidence:
    return Evidence(
        path=mapper.display_path(path),
        line=line,
        snippet=snippet,
    )


def import_evidence(path: Path, mapper: PathMapper, item) -> Evidence:
    return display_evidence(
        path,
        mapper,
        line=item.line,
        snippet=item.snippet[:300],
    )


def node_evidence(path: Path, source: str, node: Node, mapper: PathMapper) -> Evidence:
    return display_evidence(
        path,
        mapper,
        line=node.start_point.row + 1,
        snippet=node_text(source, node)[:300],
    )
