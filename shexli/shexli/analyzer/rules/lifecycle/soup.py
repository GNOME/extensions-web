# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from ....spec import R

if TYPE_CHECKING:
    from shexli.models import Evidence
from ...facts.lifecycle import (
    SoupSessionAbortFact,
    SoupSessionCreateFact,
)
from ..api import (
    ExtensionCheckContext,
    ExtensionFacts,
    ExtensionRule,
)


class LifecycleSoupRule(ExtensionRule):
    required_extension_facts = (SoupSessionCreateFact, SoupSessionAbortFact)

    def check(self, facts: ExtensionFacts, ctx: ExtensionCheckContext) -> None:
        create_fact = facts.get_fact(SoupSessionCreateFact)
        abort_fact = facts.get_fact(SoupSessionAbortFact)

        for path, create_observations in create_fact.by_path.items():
            aborted_by_scope: dict[int, set[str]] = {}
            for observation in abort_fact.by_path.get(path, []):
                aborted_by_scope.setdefault(observation.scope_id, set()).add(
                    observation.field_name
                )

            evidences: list[Evidence] = []
            for create in create_observations:
                aborted_fields = aborted_by_scope.get(create.scope_id, set())
                if create.field_name not in aborted_fields:
                    evidences.append(create.evidence)

            if evidences:
                ctx.add_finding(
                    R.EGO_L_008,
                    "Soup.Session instances should be aborted during cleanup.",
                    evidences,
                )
