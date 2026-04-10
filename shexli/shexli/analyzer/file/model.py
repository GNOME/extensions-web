# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tree_sitter import Node

from ...ast import JSImport
from ..engine import PathMapper
from .facts import (
    DeclarationCollector,
    DeclarationIndex,
    IdentifierCollector,
    ImportCollector,
)
from .indices import (
    AliasCollector,
    AliasTable,
    CallCollector,
    CallIndex,
    MemberExprCollector,
    MemberExprIndex,
    NewExprCollector,
    NewExprIndex,
)


@dataclass(slots=True)
class JSFileModel:
    """Rule-facing file model for a single analyzed JS file.

    This is the primary API for :class:`JSFileRule`. If a rule needs a new fact,
    the fact should be added to the collectors/model layer rather than
    computed ad hoc inside the rule.

    Attributes:
        path: Absolute path of the JS file.
        text: Full source text for evidence generation only.
        root: Parsed tree-sitter root node for evidence generation only.
        imports: All ES-module and legacy import records in the file.
        mapper: Path formatter used when lifecycle builds evidence directly.
        aliases: Canonical alias table for local/import aliases.
        member_expressions: Indexed member-expression facts.
        calls: Indexed call-expression facts.
        new_expressions: Indexed ``new`` expression facts.
        declarations: Top-level functions, classes, and exports.
        identifiers: Flat identifier list used by heuristic rules such as
            obfuscation checks.
    """

    path: Path
    text: str
    root: Node
    imports: list[JSImport]
    mapper: PathMapper
    aliases: AliasTable
    member_expressions: MemberExprIndex
    calls: CallIndex
    new_expressions: NewExprIndex
    declarations: DeclarationIndex
    identifiers: list[str]


class JSFileModelBuilder:
    """Thin facade that coordinates file-level collectors into a model.

    Rule authors should not call collectors directly; the builder is the place
    where file-level extraction is assembled into the stable ``JSFileModel``
    contract.
    """

    def build(
        self,
        path: Path,
        source: str,
        root: Node,
        mapper: PathMapper,
    ) -> JSFileModel:
        imports = ImportCollector().collect(source, root)
        aliases = AliasCollector().collect(source, root)
        member_expressions = MemberExprCollector().collect(source, root, aliases)
        calls = CallCollector().collect(source, root, aliases)
        declarations = DeclarationCollector().collect(source, root)
        new_expressions = NewExprCollector().collect(source, root, aliases)

        return JSFileModel(
            path=path,
            text=source,
            root=root,
            imports=imports,
            mapper=mapper,
            aliases=aliases,
            member_expressions=member_expressions,
            calls=calls,
            new_expressions=new_expressions,
            declarations=declarations,
            identifiers=IdentifierCollector().collect(root),
        )
