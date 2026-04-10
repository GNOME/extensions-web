# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from ....spec import R

if TYPE_CHECKING:
    from shexli.models import Evidence
from ...facts.lifecycle import (
    ObjectCreateFact,
    RefAssignFact,
    RefReleaseFact,
)
from ..api import (
    ExtensionCheckContext,
    ExtensionFacts,
    ExtensionRule,
)
from .common import missing_evidences, owned_descendants, release_candidates


class LifecycleReleaseRule(ExtensionRule):
    required_extension_facts = (ObjectCreateFact, RefAssignFact, RefReleaseFact)

    def check(self, facts: ExtensionFacts, ctx: ExtensionCheckContext) -> None:
        object_create_fact = facts.get_fact(ObjectCreateFact)
        assign_fact = facts.get_fact(RefAssignFact)
        release_fact = facts.get_fact(RefReleaseFact)

        for path, assign_observations in assign_fact.by_path.items():
            object_create_by_scope = {
                observation.scope_id: observation
                for observation in object_create_fact.by_path.get(path, [])
            }
            release_by_scope = {
                observation.scope_id: observation
                for observation in release_fact.by_path.get(path, [])
            }
            evidences: list[Evidence] = []

            for assign in assign_observations:
                if not assign.include_object_cleanup:
                    continue

                create = object_create_by_scope.get(assign.scope_id)
                release = release_by_scope.get(assign.scope_id)
                released_refs = {} if release is None else release.released_refs
                created_objects = {} if create is None else create.objects

                descendants = owned_descendants(
                    assign.parent_owned,
                    assign.local_parent_owned,
                )
                evidences.extend(
                    missing_evidences(
                        release_candidates(
                            created_objects,
                            assign.resource_refs,
                            assign.containers,
                            assign.release_container_names,
                        ),
                        released_refs,
                        suppress_names=descendants - assign.release_container_names,
                    )
                )

            if evidences:
                ctx.add_finding(
                    R.EGO_L_005,
                    "Owned references that are cleaned up in `disable()` should "
                    "also be released with `null` or `undefined`.",
                    evidences,
                )
