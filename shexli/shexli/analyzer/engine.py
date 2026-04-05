# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from abc import ABC, abstractmethod

from tree_sitter import Node

from ..ast import iter_nodes
from .context import CheckContext


class NodeRule(ABC):
    """Rule that visits individual AST nodes during a single traversal pass.

    ``finalize()`` is called once after the full walk so the rule can flush
    accumulated state into findings.  The default implementation is a no-op.
    """

    node_types: frozenset[str]

    @abstractmethod
    def visit(self, node: Node, text: str, ctx: CheckContext) -> None: ...

    def finalize(self, root: Node, text: str, ctx: CheckContext) -> None:
        pass


class FileRule(ABC):
    """Rule that runs once per file after the optional AST node walk."""

    @abstractmethod
    def check(self, root: Node, text: str, ctx: CheckContext) -> None: ...


class JSFileEngine:
    """
    Single-pass AST visitor that dispatches to registered rule handlers.

    NodeRule handlers are called for each matching AST node during one
    pre-order traversal of the tree.  FileRule handlers run once per file
    after the walk completes.

    Usage::

        engine = JSFileEngine(
            node_rules=[SomeNodeRule()],
            file_rules=[SomeFileRule()],
        )
        engine.run(root, text, ctx)
    """

    def __init__(
        self,
        node_rules: list[NodeRule] | None = None,
        file_rules: list[FileRule] | None = None,
    ) -> None:
        self._node_rules: list[NodeRule] = node_rules or []
        self._file_rules: list[FileRule] = file_rules or []
        self._by_type: dict[str, list[NodeRule]] = {}
        for rule in self._node_rules:
            for node_type in rule.node_types:
                self._by_type.setdefault(node_type, []).append(rule)

    def run(self, root: Node, text: str, ctx: CheckContext) -> None:
        if self._by_type:
            for node in iter_nodes(root):
                handlers = self._by_type.get(node.type)
                if handlers:
                    for handler in handlers:
                        handler.visit(node, text, ctx)
            for rule in self._node_rules:
                rule.finalize(root, text, ctx)
        for rule in self._file_rules:
            rule.check(root, text, ctx)
