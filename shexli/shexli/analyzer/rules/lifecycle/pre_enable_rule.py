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


class LifecyclePreEnableRule(ExtensionRule):
    required_extension_facts = (PreEnableObservationFact,)

    def check(self, facts: ExtensionFacts, ctx: ExtensionCheckContext) -> None:
        fact = facts.get_fact(PreEnableObservationFact)
        for observations in fact.by_path.values():
            evidences = [observation.evidence for observation in observations]
            if evidences:
                ctx.add_finding(
                    R.EGO_L_001,
                    "Resource creation or signal/source setup was found"
                    " outside `enable()`.",
                    evidences[:10],
                )
