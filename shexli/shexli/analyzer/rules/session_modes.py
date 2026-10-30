# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from ...spec import R
from ..facts.extension import (
    SessionModesExtensionFact,
)
from .api import (
    ExtensionCheckContext,
    ExtensionFacts,
    ExtensionRule,
)


class SessionModesRule(ExtensionRule):
    """ExtensionRule: EGO_M_008 — unlock-dialog must be documented in disable()."""

    required_extension_facts = (SessionModesExtensionFact,)

    def check(self, facts: ExtensionFacts, ctx: ExtensionCheckContext) -> None:
        metadata = facts.model.metadata
        package_file = facts.model.package_file(
            facts.model.EXTENSION_ENTRYPOINT_PACKAGE_PATH
        )
        path = (
            package_file.path
            if package_file is not None and package_file.path in facts.model.files
            else None
        )

        if (
            path is None
            or not metadata.is_valid
            or not metadata.session_modes
            or "unlock-dialog" not in metadata.session_modes
        ):
            return

        session_fact = facts.get_fact(SessionModesExtensionFact)
        disable_observation = session_fact.disable_observation
        if (
            disable_observation is not None
            and disable_observation.comment_evidence is not None
        ):
            return

        evidence = (
            [disable_observation.method_evidence]
            if disable_observation is not None
            else [
                ctx.display_evidence(
                    path,
                    snippet="unlock-dialog declared but disable() was not found",
                )
            ]
        )
        ctx.add_finding(
            R.EGO_M_008,
            (
                "Extensions using `unlock-dialog` should document "
                "the reason in `disable()` comments."
            ),
            evidence,
        )
