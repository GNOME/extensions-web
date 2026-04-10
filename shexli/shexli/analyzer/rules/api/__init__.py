# SPDX-License-Identifier: AGPL-3.0-or-later

"""Rule execution contract: rule base classes, facts surface, and check contexts."""

from ...engine import JSContext
from .context import ExtensionCheckContext, JSFileCheckContext
from .contract import (
    EXTENSION_RULE_TYPES,
    JS_FILE_RULE_TYPES,
    ExtensionFacts,
    ExtensionRule,
    JSFileFacts,
    JSFileRule,
)

__all__ = [
    "EXTENSION_RULE_TYPES",
    "ExtensionCheckContext",
    "ExtensionFacts",
    "ExtensionRule",
    "JSContext",
    "JS_FILE_RULE_TYPES",
    "JSFileCheckContext",
    "JSFileFacts",
    "JSFileRule",
]
