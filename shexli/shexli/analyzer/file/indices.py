# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass

from tree_sitter import Node

from ...ast import (
    call_arguments,
    call_callee_parts,
    identifier_name,
    iter_nodes,
    member_expression_parts,
    node_text,
)
from ..spawn import (
    extract_literal_argv_head,
    extract_literal_string,
    extract_spawn_argv,
)


@dataclass(frozen=True, slots=True)
class AliasTable:
    """Maps local names to canonical member-expression tuples.

    Example:
        ``const Clipboard = St.Clipboard`` allows ``Clipboard.get_default`` to
        be normalized to ``("St", "Clipboard", "get_default")``.
    """

    _mappings: dict[str, tuple[str, ...]]

    def resolve(self, name: str) -> tuple[str, ...]:
        """Resolve a single binding name to its canonical tuple."""
        return self._mappings.get(name, (name,))

    def expand(self, parts: tuple[str, ...]) -> tuple[str, ...]:
        """Expand the first segment of a member-expression tuple via aliases."""
        if not parts:
            return parts
        resolved = self._mappings.get(parts[0])
        if resolved is None:
            return parts
        return resolved + parts[1:]


class AliasCollector:
    """Single-pass AST collector that builds an :class:`AliasTable`."""

    def collect(self, source: str, root: Node) -> AliasTable:
        mappings: dict[str, tuple[str, ...]] = {}
        for node in iter_nodes(root):
            if node.type in {"lexical_declaration", "variable_declaration"}:
                _collect_var_decl(source, node, mappings)
            elif node.type == "import_statement":
                _collect_import(source, node, mappings)
        return AliasTable(mappings)


@dataclass(slots=True)
class CallSite:
    """A single call-expression fact exposed to rules.

    ``node`` and ``args`` are retained for evidence generation only. Rule code
    should prefer the precomputed fields (`arg_literals`, `arg_identifiers`,
    `arg_member_parts`, `literal_argv`, `guard_identifiers`) instead of doing
    fresh AST reasoning.
    """

    callee: tuple[str, ...]
    raw_callee: tuple[str, ...]
    node: Node
    args: list[Node]
    arg_literals: tuple[str | None, ...]
    arg_identifiers: tuple[str | None, ...]
    arg_member_parts: tuple[tuple[str, ...] | None, ...]
    literal_argv: tuple[str, ...] | None
    first_arg_argv_head: str | None
    guard_identifiers: frozenset[str]


@dataclass(frozen=True, slots=True)
class CallIndex:
    """Indexed view over all call-expression facts in a file."""

    by_callee: dict[tuple[str, ...], list[CallSite]]
    all_calls: list[CallSite]

    def find(self, *parts: str) -> list[CallSite]:
        """Return calls whose canonical callee exactly matches ``parts``."""
        return self.by_callee.get(parts, [])

    def find_suffix(self, *suffix: str) -> list[CallSite]:
        """Return calls whose canonical callee ends with ``suffix``."""
        result: list[CallSite] = []
        for callee, sites in self.by_callee.items():
            if len(callee) >= len(suffix) and callee[-len(suffix) :] == suffix:
                result.extend(sites)
        return result


class CallCollector:
    """Single-pass AST collector that builds a :class:`CallIndex`."""

    def collect(
        self,
        source: str,
        root: Node,
        aliases: AliasTable | None = None,
    ) -> CallIndex:
        by_callee: dict[tuple[str, ...], list[CallSite]] = {}
        all_calls: list[CallSite] = []
        for node in iter_nodes(root):
            if node.type != "call_expression":
                continue
            function_node = node.child_by_field_name("function")
            if function_node is None:
                continue
            raw_parts = call_callee_parts(source, node)
            if not raw_parts:
                continue
            raw_callee = tuple(raw_parts)
            args = call_arguments(node)
            callee = (
                aliases.expand(tuple(raw_parts))
                if aliases is not None
                else tuple(raw_parts)
            )
            site = CallSite(
                callee=callee,
                raw_callee=raw_callee,
                node=node,
                args=args,
                arg_literals=tuple(extract_literal_string(source, arg) for arg in args),
                arg_identifiers=tuple(identifier_name(source, arg) for arg in args),
                arg_member_parts=tuple(
                    tuple(parts)
                    if (parts := member_expression_parts(source, arg))
                    else None
                    for arg in args
                ),
                literal_argv=(
                    tuple(argv)
                    if (argv := extract_spawn_argv(source, node)) is not None
                    else None
                ),
                first_arg_argv_head=(
                    extract_literal_argv_head(source, args[0]) if args else None
                ),
                guard_identifiers=_guard_identifiers(source, node),
            )
            all_calls.append(site)
            by_callee.setdefault(callee, []).append(site)
        return CallIndex(by_callee, all_calls)


@dataclass(slots=True)
class MemberExprSite:
    """A single member expression exposed through the file model."""

    parts: tuple[str, ...]
    raw_parts: tuple[str, ...]
    node: Node


@dataclass(frozen=True, slots=True)
class MemberExprIndex:
    """Indexed view over all member expressions in a file."""

    by_parts: dict[tuple[str, ...], list[MemberExprSite]]
    all_member_exprs: list[MemberExprSite]

    def find(self, *parts: str) -> list[MemberExprSite]:
        """Return member expressions matching canonical alias-expanded parts."""
        return self.by_parts.get(parts, [])

    def find_prefix(self, *prefix: str) -> list[MemberExprSite]:
        """Return member expressions whose canonical parts start with `prefix`."""
        result: list[MemberExprSite] = []
        for parts, sites in self.by_parts.items():
            if len(parts) >= len(prefix) and parts[: len(prefix)] == prefix:
                result.extend(sites)
        return result


class MemberExprCollector:
    """Single-pass AST collector that builds a :class:`MemberExprIndex`."""

    def collect(
        self,
        source: str,
        root: Node,
        aliases: AliasTable | None = None,
    ) -> MemberExprIndex:
        by_parts: dict[tuple[str, ...], list[MemberExprSite]] = {}
        all_member_exprs: list[MemberExprSite] = []
        for node in iter_nodes(root):
            if node.type != "member_expression":
                continue
            raw_parts = member_expression_parts(source, node)
            if not raw_parts:
                continue
            raw = tuple(raw_parts)
            parts = aliases.expand(raw) if aliases is not None else raw
            site = MemberExprSite(parts=parts, raw_parts=raw, node=node)
            all_member_exprs.append(site)
            by_parts.setdefault(parts, []).append(site)
        return MemberExprIndex(by_parts=by_parts, all_member_exprs=all_member_exprs)


@dataclass(slots=True)
class NewExprSite:
    """A single ``new`` expression fact exposed to rules."""

    ctor: tuple[str, ...]
    raw_ctor: tuple[str, ...]
    node: Node


@dataclass(frozen=True, slots=True)
class NewExprIndex:
    """Indexed view over all ``new`` expression facts in a file.

    Constructor tuples are canonicalized through the alias table in the same
    way as call and member-expression indices.
    """

    by_ctor: dict[tuple[str, ...], list[NewExprSite]]
    all_new_exprs: list[NewExprSite]

    def find(self, *parts: str) -> list[NewExprSite]:
        """Return ``new`` sites whose canonical constructor matches ``parts``."""
        return self.by_ctor.get(parts, [])


class NewExprCollector:
    """Single-pass AST collector that builds a :class:`NewExprIndex`."""

    def collect(
        self,
        source: str,
        root: Node,
        aliases: AliasTable | None = None,
    ) -> NewExprIndex:
        by_ctor: dict[tuple[str, ...], list[NewExprSite]] = {}
        all_new_exprs: list[NewExprSite] = []
        for node in iter_nodes(root):
            if node.type != "new_expression":
                continue
            ctor_node = node.child_by_field_name("constructor")
            if ctor_node is None:
                continue
            raw_parts = member_expression_parts(source, ctor_node)
            if not raw_parts:
                continue
            raw_ctor = tuple(raw_parts)
            ctor = (
                aliases.expand(tuple(raw_parts))
                if aliases is not None
                else tuple(raw_parts)
            )
            site = NewExprSite(ctor=ctor, raw_ctor=raw_ctor, node=node)
            all_new_exprs.append(site)
            by_ctor.setdefault(ctor, []).append(site)
        return NewExprIndex(by_ctor, all_new_exprs)


def _collect_var_decl(
    source: str,
    decl: Node,
    out: dict[str, tuple[str, ...]],
) -> None:
    for child in decl.named_children:
        if child.type != "variable_declarator":
            continue
        name_node = child.child_by_field_name("name")
        value_node = child.child_by_field_name("value")
        if name_node is None or value_node is None:
            continue

        if name_node.type == "identifier":
            parts = member_expression_parts(source, value_node)
            if parts:
                out[node_text(source, name_node)] = tuple(parts)

        elif name_node.type == "object_pattern":
            rhs_parts = member_expression_parts(source, value_node)
            if not rhs_parts:
                continue
            rhs = tuple(rhs_parts)
            _collect_object_pattern(source, name_node, rhs, out)


def _collect_object_pattern(
    source: str,
    pattern: Node,
    rhs: tuple[str, ...],
    out: dict[str, tuple[str, ...]],
) -> None:
    for child in pattern.named_children:
        if child.type == "shorthand_property_identifier_pattern":
            prop = node_text(source, child)
            out[prop] = rhs + (prop,)
        elif child.type == "pair_pattern":
            key_node = child.child_by_field_name("key")
            val_node = child.child_by_field_name("value")
            if key_node is None or val_node is None:
                continue
            if val_node.type != "identifier":
                continue
            prop = node_text(source, key_node)
            binding = node_text(source, val_node)
            out[binding] = rhs + (prop,)


def _collect_import(
    source: str,
    stmt: Node,
    out: dict[str, tuple[str, ...]],
) -> None:
    namespace: str | None = None
    for child in stmt.children:
        if child.type == "string":
            raw = node_text(source, child).strip("\"'")
            if raw.startswith("gi://"):
                namespace = raw[len("gi://") :]
            break

    for child in iter_nodes(stmt):
        if child.type == "import_specifier":
            name_node = child.child_by_field_name("name")
            alias_node = child.child_by_field_name("alias")
            if name_node is None or alias_node is None:
                continue
            export_name = node_text(source, name_node)
            local_name = node_text(source, alias_node)
            if namespace is not None:
                out[local_name] = (namespace, export_name)
            else:
                out[local_name] = (export_name,)


def spawn_argv_arg(call_name: str, args: list[Node]) -> Node | None:
    if not args:
        return None
    if call_name in {
        "Gio.Subprocess.new",
        "GLib.spawn_command_line_async",
        "GLib.spawn_command_line_sync",
    }:
        return args[0]
    if call_name in {"GLib.spawn_async", "GLib.spawn_async_with_pipes"}:
        return args[1] if len(args) > 1 else None
    if call_name.startswith("Shell.Util."):
        return args[0]
    return None


def _guard_identifiers(source: str, node: Node) -> frozenset[str]:
    names: set[str] = set()
    prev = node
    current = node.parent
    while current is not None:
        if current.type == "if_statement":
            cond = current.child_by_field_name("condition")
            consequence = current.child_by_field_name("consequence")
            if (
                cond is not None
                and consequence is not None
                and _contains_node(consequence, prev)
            ):
                names.update(_condition_identifiers(source, cond))
        prev = current
        current = current.parent
    return frozenset(names)


def _condition_identifiers(source: str, node: Node) -> set[str]:
    names: set[str] = set()
    if node.type == "identifier":
        if node.text is not None:
            names.add(node.text.decode())
        return names
    if node.type == "member_expression":
        parts = member_expression_parts(source, node)
        names.update(parts)
        prop = node.child_by_field_name("property")
        if prop is not None and prop.text is not None:
            names.add(prop.text.decode())
        return names
    if node.type in {"unary_expression", "parenthesized_expression"}:
        for child in node.children:
            names.update(_condition_identifiers(source, child))
        return names
    for child in node.children:
        names.update(_condition_identifiers(source, child))
    return names


def _contains_node(parent: Node, child: Node) -> bool:
    return parent.start_byte <= child.start_byte and child.end_byte <= parent.end_byte
