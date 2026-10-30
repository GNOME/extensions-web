# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from ...spec import R
from ..facts.extension import (
    PrefsExtensionFact,
)
from .api import (
    ExtensionCheckContext,
    ExtensionFacts,
    ExtensionRule,
)


class PrefsRule(ExtensionRule):
    """ExtensionRule: EGO_C45_001/EGO_L_006.

    Covers getPreferencesWidget and retained prefs fields.
    """

    required_extension_facts = (PrefsExtensionFact,)

    def check(self, facts: ExtensionFacts, ctx: ExtensionCheckContext) -> None:
        package_file = facts.model.package_file(
            facts.model.PREFERENCES_ENTRYPOINT_PACKAGE_PATH
        )
        if package_file is None or package_file.path not in facts.model.files:
            return

        prefs_fact = facts.get_fact(PrefsExtensionFact)
        widget_method_evidences = [
            observation.evidence
            for observation in prefs_fact.method_observations
            if observation.name == "getPreferencesWidget"
        ]
        retained_assignment_evidences = [
            observation.evidence
            for observation in prefs_fact.state_assignment_observations
        ]
        has_cleanup = bool(prefs_fact.cleanup_observations)

        if any(version >= 45 for version in facts.model.target_versions):
            if widget_method_evidences:
                ctx.add_finding(
                    R.EGO_C45_001,
                    (
                        "45+ preferences code should use `fillPreferencesWindow()` "
                        "instead of `getPreferencesWidget()`."
                    ),
                    widget_method_evidences,
                )

        if retained_assignment_evidences and not has_cleanup:
            ctx.add_finding(
                R.EGO_L_006,
                (
                    "Preferences code stores window-scoped objects on the "
                    "exported prefs class without `close-request` cleanup."
                ),
                retained_assignment_evidences[:10],
            )
