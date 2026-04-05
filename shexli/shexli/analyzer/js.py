# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from ..ast import (
    imports_in_program,
    legacy_imports_in_program,
    parse_js,
)
from .compat import ApiMisuseRule, SubprocessRule, VersionCompatRule
from .context import CheckContext
from .engine import JSFileEngine
from .rules.clipboard import ClipboardRule
from .rules.imports import (
    DeprecatedImportsRule,
    ForbiddenLibsRule,
    ImportsGiRule,
)
from .rules.lifecycle import LifecycleRule
from .rules.logging import ExcessiveLoggingRule
from .rules.obfuscation import ObfuscationRule
from .rules.prefs import PrefsRule
from .rules.session_modes import SessionModesRule


def check_js_file(
    ctx: CheckContext,
    text: str,
    metadata: dict | None,
    target_versions: set[int],
    contexts: set[str],
) -> None:
    ctx.target_versions = target_versions
    ctx.file_contexts = contexts

    tree = parse_js(text)
    root = tree.root_node
    js_imports = imports_in_program(text, root) + legacy_imports_in_program(text, root)

    JSFileEngine(
        node_rules=[
            ImportsGiRule(),
            ClipboardRule(),
        ],
        file_rules=[
            DeprecatedImportsRule(js_imports),
            ForbiddenLibsRule(js_imports),
            PrefsRule(metadata),
            SessionModesRule(metadata),
            LifecycleRule(),
            SubprocessRule(),
            ApiMisuseRule(),
            VersionCompatRule(js_imports),
            ExcessiveLoggingRule(),
            ObfuscationRule(),
        ],
    ).run(root, text, ctx)
