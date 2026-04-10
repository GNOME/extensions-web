# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass

from tree_sitter import Node

from ..file.facts import (
    PrefsFactsCollector,
    SessionModesFactsCollector,
    SpawnWrapperCollector,
    StylesheetBindingCollector,
)
from .base import JSFileFactBuilder, JSFileFactContext


@dataclass(frozen=True, slots=True)
class StylesheetBindingFact:
    """Bindings that resolve to the package `stylesheet.css` path.

    Attributes:
        bindings: Local binding names that resolve to `stylesheet.css`.
    """

    bindings: frozenset[str]


@dataclass(frozen=True, slots=True)
class SpawnWrapperFact:
    """Locally declared wrapper function names that spawn subprocesses.

    Attributes:
        wrappers: Wrapper function names that eventually invoke subprocess
            spawning helpers.
    """

    wrappers: frozenset[str]


@dataclass(frozen=True, slots=True)
class FileShapeFact:
    """Reusable whole-file heuristics for layout and identifier shape.

    Attributes:
        file_size_bytes: UTF-8 encoded byte size of the source file.
        non_empty_line_count: Number of non-blank lines.
        scored_identifier_count: Number of identifiers considered by the
            short-name heuristic after excluding conventional short names.
        short_identifier_ratio: Fraction of scored identifiers that are 1-2
            characters long.
        avg_identifier_length: Average length of scored identifiers.
    """

    file_size_bytes: int
    non_empty_line_count: int
    scored_identifier_count: int
    short_identifier_ratio: float | None
    avg_identifier_length: float | None


@dataclass(frozen=True, slots=True)
class PrefsFact:
    """Preferences observations derived from `prefs.js`.

    Attributes:
        get_preferences_widget_nodes: Method declarations named
            `getPreferencesWidget`.
        state_assignment_nodes: Assignments that retain values on the exported
            preferences object.
        close_request_cleanup_nodes: Cleanup handlers attached to the
            `close-request` signal.
    """

    get_preferences_widget_nodes: list[Node]
    state_assignment_nodes: list[Node]
    close_request_cleanup_nodes: list[Node]


@dataclass(frozen=True, slots=True)
class SessionModesFact:
    """disable() and comment observations derived from `extension.js`.

    Attributes:
        disable_method_nodes: `disable()` method declarations found in the
            extension entrypoint.
        commented_disable_nodes: AST nodes inside `disable()` that carry nearby
            comments suitable for documentation evidence.
    """

    disable_method_nodes: list[Node]
    commented_disable_nodes: list[Node]


class StylesheetBindingFactBuilder(JSFileFactBuilder[StylesheetBindingFact]):
    """Build stylesheet-binding observations for one analyzed JS file."""

    fact_type = StylesheetBindingFact

    def build(self, ctx: JSFileFactContext) -> StylesheetBindingFact:
        """Collect local bindings that resolve to `stylesheet.css`."""
        bindings = StylesheetBindingCollector().collect(ctx.file.text, ctx.file.calls)
        return StylesheetBindingFact(bindings=bindings)


class FileShapeFactBuilder(JSFileFactBuilder[FileShapeFact]):
    """Build reusable whole-file heuristics for one analyzed JS file."""

    fact_type = FileShapeFact

    def build(self, ctx: JSFileFactContext) -> FileShapeFact:
        """Compute reusable whole-file layout and identifier heuristics."""
        text = ctx.file.text
        file_size_bytes = len(text.encode())
        non_empty_line_count = len([line for line in text.splitlines() if line.strip()])

        conventional_single = {
            "_",
            "i",
            "j",
            "k",
            "n",
            "x",
            "y",
            "e",
            "t",
            "s",
            "v",
            "r",
            "p",
        }
        scored = [
            identifier
            for identifier in ctx.file.identifiers
            if identifier not in conventional_single
        ]
        if scored:
            short = sum(1 for identifier in scored if len(identifier) <= 2)
            short_identifier_ratio = short / len(scored)
            avg_identifier_length = sum(len(identifier) for identifier in scored) / len(
                scored
            )
        else:
            short_identifier_ratio = None
            avg_identifier_length = None

        return FileShapeFact(
            file_size_bytes=file_size_bytes,
            non_empty_line_count=non_empty_line_count,
            scored_identifier_count=len(scored),
            short_identifier_ratio=short_identifier_ratio,
            avg_identifier_length=avg_identifier_length,
        )


class SpawnWrapperFactBuilder(JSFileFactBuilder[SpawnWrapperFact]):
    """Build subprocess-wrapper observations for one analyzed JS file."""

    fact_type = SpawnWrapperFact

    def build(self, ctx: JSFileFactContext) -> SpawnWrapperFact:
        """Collect local wrappers around subprocess-spawning calls."""
        wrappers = SpawnWrapperCollector().collect(
            ctx.file.text,
            ctx.file.declarations,
        )
        return SpawnWrapperFact(wrappers=wrappers)


class PrefsFactBuilder(JSFileFactBuilder[PrefsFact]):
    """Build preferences AST observations for one analyzed JS file."""

    fact_type = PrefsFact

    def build(self, ctx: JSFileFactContext) -> PrefsFact:
        """Collect reusable AST observations from `prefs.js`."""
        prefs = PrefsFactsCollector().collect(
            ctx.file.text,
            ctx.file.root,
            ctx.file.path,
        )
        return PrefsFact(
            get_preferences_widget_nodes=prefs.get_preferences_widget_nodes,
            state_assignment_nodes=prefs.state_assignment_nodes,
            close_request_cleanup_nodes=prefs.close_request_cleanup_nodes,
        )


class SessionModesFactBuilder(JSFileFactBuilder[SessionModesFact]):
    """Build session-modes AST observations for one analyzed JS file."""

    fact_type = SessionModesFact

    def build(self, ctx: JSFileFactContext) -> SessionModesFact:
        """Collect `disable()` and comment observations from `extension.js`."""
        session_modes = SessionModesFactsCollector().collect(
            ctx.file.text,
            ctx.file.root,
            ctx.file.path,
        )
        return SessionModesFact(
            disable_method_nodes=session_modes.disable_method_nodes,
            commented_disable_nodes=session_modes.commented_disable_nodes,
        )
