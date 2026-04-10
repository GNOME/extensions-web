# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from ...engine import JSContext

if TYPE_CHECKING:
    from tree_sitter import Node

    from shexli.ast import JSImport
    from shexli.models import Evidence, Finding


class JSFileCheckContext:
    """Emission-only execution context for :class:`JSFileRule`.

    Carries runtime state needed to emit findings and build evidence.
    Does not expose models, fact stores, or fact resolution methods —
    those live in :class:`JSFileFacts`.

    Attributes:
        path: Absolute path of the analyzed JS file.
        target_versions: GNOME Shell major versions declared by the current
            extension.
        contexts: Reachability-derived execution contexts for the current file.
    """

    __slots__ = (
        "path",
        "target_versions",
        "contexts",
        "_make_finding",
        "_add_finding",
        "_display_evidence",
        "_import_evidence",
        "_node_evidence",
    )

    path: Path
    target_versions: set[int]
    contexts: set[JSContext]

    def __init__(
        self,
        *,
        path: Path,
        make_finding: Callable[[str, str, list[Evidence] | None], Finding],
        add_finding: Callable[[Finding], None],
        display_evidence: Callable[..., Evidence],
        import_evidence: Callable[[JSImport], Evidence],
        node_evidence: Callable[[str, Node], Evidence],
        target_versions: set[int] | None = None,
        contexts: set[JSContext] | None = None,
    ) -> None:
        """Create a file-rule execution context.

        Args:
            path: Absolute path of the analyzed JS file.
            make_finding: Finding factory for the given rule id and message.
            add_finding: Sink that records one emitted finding.
            display_evidence: Evidence builder for display-only snippets.
            import_evidence: Evidence builder for import statements.
            node_evidence: Evidence builder for AST nodes in the current file.
            target_versions: Optional initial shell-version set.
            contexts: Optional initial reachability contexts for the file.
        """
        self.path = path
        self.target_versions = set() if target_versions is None else target_versions
        self.contexts = set() if contexts is None else contexts
        self._make_finding = make_finding
        self._add_finding = add_finding
        self._display_evidence = display_evidence
        self._import_evidence = import_evidence
        self._node_evidence = node_evidence

    def add_finding(self, rule_id: str, message: str, evidence=None) -> None:
        """Emit one finding for the current file rule."""
        self._add_finding(self._make_finding(rule_id, message, evidence))

    def display_evidence(
        self, *, line: int | None = None, snippet: str = ""
    ) -> Evidence:
        """Build display-only evidence for the current file."""
        return self._display_evidence(line=line, snippet=snippet)

    def import_evidence(self, item: JSImport) -> Evidence:
        """Build evidence pointing at one import statement."""
        return self._import_evidence(item)

    def node_evidence(self, source: str, node: Node) -> Evidence:
        """Build evidence for one AST node in the current file."""
        return self._node_evidence(source, node)


class ExtensionCheckContext:
    """Emission-only execution context for :class:`ExtensionRule`."""

    __slots__ = ("_make_finding", "_add_finding", "_display_evidence")

    def __init__(
        self,
        *,
        make_finding: Callable[[str, str, list[Evidence] | None], Finding],
        add_finding: Callable[[Finding], None],
        display_evidence: Callable[[Path], Callable[..., Evidence]],
    ) -> None:
        """Create an extension-rule execution context.

        Args:
            make_finding: Finding factory for the given rule id and message.
            add_finding: Sink that records one emitted finding.
            display_evidence: Evidence builder factory for package files.
        """
        self._make_finding = make_finding
        self._add_finding = add_finding
        self._display_evidence = display_evidence

    def add_finding(self, rule_id: str, message: str, evidence=None) -> None:
        """Emit one finding for the current extension rule."""
        self._add_finding(self._make_finding(rule_id, message, evidence))

    def display_evidence(
        self, path: Path, *, line: int | None = None, snippet: str = ""
    ) -> Evidence:
        """Build display-only evidence for a package file."""
        return self._display_evidence(path)(line=line, snippet=snippet)
