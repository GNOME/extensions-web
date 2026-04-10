# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from ....spec import R

if TYPE_CHECKING:
    from shexli.models import Evidence
from ...facts.lifecycle import (
    ObjectCreateFact,
    ObjectDestroyFact,
)
from ..api import (
    ExtensionCheckContext,
    ExtensionFacts,
    ExtensionRule,
)
from .common import is_prefs_only_context, missing_evidences, owned_descendants


class LifecycleObjectsRule(ExtensionRule):
    required_extension_facts = (ObjectCreateFact, ObjectDestroyFact)

    def check(self, facts: ExtensionFacts, ctx: ExtensionCheckContext) -> None:
        create_fact = facts.get_fact(ObjectCreateFact)
        destroy_fact = facts.get_fact(ObjectDestroyFact)

        for path, create_observations in create_fact.by_path.items():
            if is_prefs_only_context(facts.model, path):
                continue
            destroy_by_scope = {
                observation.scope_id: observation
                for observation in destroy_fact.by_path.get(path, [])
            }
            evidences: list[Evidence] = []

            for create in create_observations:
                if not create.include_object_cleanup:
                    continue

                destroy = destroy_by_scope.get(create.scope_id)
                destroyed_objects = {} if destroy is None else destroy.objects
                destroyed_object_groups = (
                    {} if destroy is None else destroy.object_groups
                )

                suppress_names = (
                    owned_descendants(
                        create.parent_owned,
                        create.local_parent_owned,
                    )
                    | create.suppress_root_fields
                )

                evidences.extend(
                    missing_evidences(
                        create.objects,
                        destroyed_objects,
                        suppress_names=suppress_names,
                    )
                )
                evidences.extend(
                    missing_evidences(
                        create.object_groups,
                        destroyed_object_groups,
                        suppress_names=suppress_names,
                    )
                )

            if evidences:
                ctx.add_finding(
                    R.EGO_L_002,
                    "Objects assigned in `enable()` are missing matching "
                    "`.destroy()` calls in `disable()` or its helper methods.",
                    evidences,
                )
