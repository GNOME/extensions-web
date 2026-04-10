# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from inspect import isabstract
from typing import TYPE_CHECKING, TypeVar, cast

from .context import ExtensionCheckContext, JSFileCheckContext

if TYPE_CHECKING:
    from ...engine import ExtensionModel
    from ...file.model import JSFileModel

FactT = TypeVar("FactT")
JS_FILE_RULE_TYPES: list[type[JSFileRule]] = []
EXTENSION_RULE_TYPES: list[type[ExtensionRule]] = []


class JSFileFacts:
    """Unified data surface for :class:`JSFileRule`.

    Attributes:
        model: Rule-facing file model for the current JS file.
    """

    __slots__ = ("model", "_get_fact")

    def __init__(
        self,
        model: JSFileModel,
        get_fact: Callable[[type[object]], object],
    ) -> None:
        """Create a rule-facing facts surface for one analyzed JS file."""
        self.model = model
        self._get_fact = get_fact

    def get_fact(self, fact_type: type[FactT]) -> FactT:
        """Return the requested file fact with the same type as `fact_type`."""
        return cast(FactT, self._get_fact(fact_type))


class ExtensionFacts:
    """Unified data surface for :class:`ExtensionRule`.

    Attributes:
        model: Rule-facing extension model for the current package.
    """

    __slots__ = ("model", "_get_fact")

    def __init__(
        self,
        model: ExtensionModel,
        get_fact: Callable[[type[object]], object],
    ) -> None:
        """Create a rule-facing facts surface for one analyzed extension."""
        self.model = model
        self._get_fact = get_fact

    def get_fact(self, fact_type: type[FactT]) -> FactT:
        """Return the requested extension fact with the same type as `fact_type`."""
        return cast(FactT, self._get_fact(fact_type))


class JSFileRule(ABC):
    """Rule that runs once per JS file.

    Attributes:
        applies_to_versions: Optional shell-version filter for the rule.
        required_file_facts: File facts that must be built before ``check()``.
    """

    applies_to_versions: frozenset[int] | None = None
    required_file_facts: tuple[type[object], ...] = ()

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if not isabstract(cls):
            JS_FILE_RULE_TYPES.append(cls)

    def applies(self, ctx: JSFileCheckContext) -> bool:
        """Return whether the rule should run for the current file context."""
        if self.applies_to_versions is None:
            return True
        return bool(self.applies_to_versions & ctx.target_versions)

    @abstractmethod
    def check(self, facts: JSFileFacts, ctx: JSFileCheckContext) -> None:
        """Inspect one analyzed file and emit findings through ``ctx``."""
        ...


class ExtensionRule(ABC):
    """Rule that runs once per extension against extension-level facts.

    Attributes:
        applies_to_versions: Optional shell-version filter for the rule.
        required_extension_facts: Extension facts that must be built before
            ``check()``.
    """

    applies_to_versions: frozenset[int] | None = None
    required_extension_facts: tuple[type[object], ...] = ()

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if not isabstract(cls):
            EXTENSION_RULE_TYPES.append(cls)

    def applies(self, model: ExtensionModel) -> bool:
        """Return whether the rule should run for the current extension."""
        if self.applies_to_versions is None:
            return True
        return bool(self.applies_to_versions & model.target_versions)

    @abstractmethod
    def check(self, facts: ExtensionFacts, ctx: ExtensionCheckContext) -> None:
        """Inspect one analyzed extension and emit findings through ``ctx``."""
        ...
