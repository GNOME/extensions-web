# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from ....spec import R

if TYPE_CHECKING:
    from shexli.models import Evidence
from ...facts.lifecycle import (
    SourceAddFact,
    SourceRecreateFact,
    SourceRemoveFact,
)
from ..api import (
    ExtensionCheckContext,
    ExtensionFacts,
    ExtensionRule,
)
from .common import is_prefs_only_context, missing_evidences


class LifecycleSourcesRule(ExtensionRule):
    required_extension_facts = (SourceAddFact, SourceRemoveFact, SourceRecreateFact)

    def check(self, facts: ExtensionFacts, ctx: ExtensionCheckContext) -> None:
        add_fact = facts.get_fact(SourceAddFact)
        remove_fact = facts.get_fact(SourceRemoveFact)
        recreate_fact = facts.get_fact(SourceRecreateFact)

        for path, add_observations in add_fact.by_path.items():
            if is_prefs_only_context(facts.model, path):
                continue
            remove_by_scope = {
                observation.scope_id: observation
                for observation in remove_fact.by_path.get(path, [])
            }
            recreate_by_scope = {
                observation.scope_id: observation
                for observation in recreate_fact.by_path.get(path, [])
            }

            missing_cleanup_evidences: list[Evidence] = []
            recreated_source_evidences: list[Evidence] = []

            for add in add_observations:
                remove = remove_by_scope.get(add.scope_id)
                recreated = recreate_by_scope.get(add.scope_id)
                cleaned_sources = {} if remove is None else remove.sources
                cleaned_source_groups = {} if remove is None else remove.source_groups

                missing_cleanup_evidences.extend(
                    missing_evidences(add.sources, cleaned_sources)
                )
                missing_cleanup_evidences.extend(
                    missing_evidences(add.source_groups, cleaned_source_groups)
                )

                if recreated is not None:
                    recreated_source_evidences.extend(
                        evidence
                        for evidence in recreated.recreated_sources.values()
                        if evidence is not None
                    )

            if missing_cleanup_evidences:
                ctx.add_finding(
                    R.EGO_L_004,
                    "Main loop sources assigned in `enable()` are missing "
                    "matching removals in `disable()` or its helper methods.",
                    missing_cleanup_evidences,
                )
            if recreated_source_evidences:
                ctx.add_finding(
                    R.EGO_L_007,
                    "Main loop sources should be removed before creating a "
                    "new source on the same field.",
                    recreated_source_evidences,
                )
