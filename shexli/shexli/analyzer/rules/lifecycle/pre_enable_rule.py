# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from ....spec import R
from ...facts.lifecycle import (
    PreEnableObservationFact,
)
from ..api import (
    ExtensionCheckContext,
    ExtensionFacts,
    ExtensionRule,
)
from .common import is_prefs_only_context


class LifecyclePreEnableRule(ExtensionRule):
    required_extension_facts = (PreEnableObservationFact,)

    def check(self, facts: ExtensionFacts, ctx: ExtensionCheckContext) -> None:
        fact = facts.get_fact(PreEnableObservationFact)
        for path, observations in fact.by_path.items():
            if is_prefs_only_context(facts.model, path):
                continue
            evidences = [observation.evidence for observation in observations]
            if evidences:
                ctx.add_finding(
                    R.EGO_L_001,
                    "Resource creation or signal/source setup was found"
                    " outside `enable()`.",
                    evidences[:10],
                )
