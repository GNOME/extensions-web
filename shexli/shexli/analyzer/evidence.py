# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from pathlib import Path

from tree_sitter import Node

from ..ast import node_text
from ..models import Evidence
from .paths import PathMapper


def format_node_snippet(source: str, node: Node, *, limit: int = 300) -> str:
    snippet = node_text(source, node)

    if "\n" in snippet:
        source_bytes = source.encode("utf-8")
        line_start = source_bytes.rfind(b"\n", 0, node.start_byte) + 1
        line_prefix = source_bytes[line_start : node.start_byte].decode("utf-8")
        if line_prefix.isspace():
            snippet = f"{line_prefix}{snippet}"

    return snippet[:limit]


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
        snippet=format_node_snippet(source, node),
    )
