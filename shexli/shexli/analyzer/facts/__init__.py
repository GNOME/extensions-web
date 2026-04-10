# SPDX-License-Identifier: AGPL-3.0-or-later

"""Derived analyzer fact infrastructure."""

from . import extension as _extension
from . import file as _file
from . import lifecycle as _lifecycle
from .base import (
    EXTENSION_FACT_BUILDERS,
    FILE_FACT_BUILDERS,
    ExtensionFactBuilder,
    ExtensionFactContext,
    FactStore,
    JSFileFactBuilder,
    JSFileFactContext,
)

_FACT_MODULES = (_extension, _file, _lifecycle)

__all__ = [
    "EXTENSION_FACT_BUILDERS",
    "ExtensionFactBuilder",
    "ExtensionFactContext",
    "FILE_FACT_BUILDERS",
    "FactStore",
    "JSFileFactBuilder",
    "JSFileFactContext",
]
