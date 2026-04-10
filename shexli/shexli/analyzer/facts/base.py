# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from inspect import isabstract
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from ..engine import ExtensionModel
    from ..file import JSFileModel

T = TypeVar("T")
FILE_FACT_BUILDERS: dict[type[object], JSFileFactBuilder[Any]] = {}
EXTENSION_FACT_BUILDERS: dict[type[object], ExtensionFactBuilder[Any]] = {}


@dataclass(frozen=True, slots=True)
class JSFileFactContext:
    """Context passed to file fact builders.

    Fact builders consume already-built analyzer models and other derived
    facts. They must not reach back into rule code or mutate the fact store.
    """

    file: JSFileModel
    """Analyzed JS file model for the file being built."""

    extension: ExtensionModel
    """Owning extension model for the current file."""

    store: FactStore
    """Shared fact cache used to resolve dependent facts."""

    def get_file_fact(self, fact_type: type[T], /) -> T:
        """Return another fact for the current JS file."""
        return self.store.get_file_fact(self.file.path, fact_type)

    def get_extension_fact(self, fact_type: type[T], /) -> T:
        """Return an extension-level fact while building a file fact."""
        return self.store.get_extension_fact(fact_type)


@dataclass(frozen=True, slots=True)
class ExtensionFactContext:
    """Context passed to extension fact builders.

    Attributes:
        extension: Extension model being analyzed.
        store: Shared fact cache used to resolve dependent facts.
    """

    extension: ExtensionModel
    """Extension model being analyzed."""

    store: FactStore
    """Shared fact cache used to resolve dependent facts."""

    def get_file_fact(self, path: Path, fact_type: type[T], /) -> T:
        """Aggregate a file-level fact into an extension-level fact builder."""
        return self.store.get_file_fact(path, fact_type)

    def get_extension_fact(self, fact_type: type[T], /) -> T:
        """Return another extension-level fact."""
        return self.store.get_extension_fact(fact_type)


class JSFileFactBuilder(ABC, Generic[T]):
    """Builds one typed file fact from a JSFileModel and other cached facts.

    Rule authors should add a builder instead of hiding file analysis inside a
    rule. Builders may depend on other facts through the provided context.
    """

    fact_type: type[T]
    """Concrete fact type produced by this builder."""

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if isabstract(cls):
            return
        fact_type = getattr(cls, "fact_type", None)
        if fact_type is None:
            return
        FILE_FACT_BUILDERS[fact_type] = cls()

    @abstractmethod
    def build(self, ctx: JSFileFactContext) -> T:
        """Build the declared fact for the current JS file."""
        ...


class ExtensionFactBuilder(ABC, Generic[T]):
    """Builds one typed extension fact from an ExtensionModel.

    Attributes:
        fact_type: Concrete fact type produced by this builder.
    """

    fact_type: type[T]
    """Concrete fact type produced by this builder."""

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if isabstract(cls):
            return
        fact_type = getattr(cls, "fact_type", None)
        if fact_type is None:
            return
        EXTENSION_FACT_BUILDERS[fact_type] = cls()

    @abstractmethod
    def build(self, ctx: ExtensionFactContext) -> T:
        """Build the declared fact for the current extension."""
        ...


class FactStore:
    """Lazy cache for file and extension derived facts.

    Builders run at most once per fact key. Repeated requests hit the cache and
    reuse the already built value.

    This is the shared bridge between declared rule dependencies and concrete
    fact builders. Runtime code should route fact access through this store
    rather than constructing builders ad hoc.
    """

    def __init__(
        self,
        extension_model: ExtensionModel,
        *,
        file_fact_builders: Mapping[type[object], JSFileFactBuilder[Any]] | None = None,
        extension_fact_builders: Mapping[type[object], ExtensionFactBuilder[Any]]
        | None = None,
    ) -> None:
        self._extension_model = extension_model
        self._file_fact_builders = file_fact_builders or {}
        self._extension_fact_builders = extension_fact_builders or {}
        self._file_cache: dict[tuple[object, type[object]], object] = {}
        self._extension_cache: dict[type[object], object] = {}

    def get_file_fact(self, path, fact_type: type[T], /) -> T:
        """Return one cached or newly built file fact."""
        key = (path, fact_type)
        if key not in self._file_cache:
            builder = self._file_fact_builders.get(fact_type)
            if builder is None:
                raise KeyError(f"No file fact builder registered for {fact_type!r}")

            file_model = self._extension_model.files[path]
            ctx = JSFileFactContext(
                file=file_model,
                extension=self._extension_model,
                store=self,
            )
            self._file_cache[key] = builder.build(ctx)

        return self._file_cache[key]  # type: ignore[return-value]

    def get_extension_fact(self, fact_type: type[T], /) -> T:
        """Return one cached or newly built extension fact."""
        if fact_type not in self._extension_cache:
            builder = self._extension_fact_builders.get(fact_type)
            if builder is None:
                raise KeyError(
                    f"No extension fact builder registered for {fact_type!r}"
                )

            ctx = ExtensionFactContext(extension=self._extension_model, store=self)
            self._extension_cache[fact_type] = builder.build(ctx)

        return self._extension_cache[fact_type]  # type: ignore[return-value]
