# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from ....spec import R

if TYPE_CHECKING:
    from shexli.models import Evidence

from ...facts.lifecycle import (
    SignalConnectFact,
    SignalDisconnectFact,
)
from ..api import (
    ExtensionCheckContext,
    ExtensionFacts,
    ExtensionRule,
)
from .common import (
    is_prefs_only_context,
    missing_evidences,
    owned_descendants,
)


class LifecycleSignalsRule(ExtensionRule):
    required_extension_facts = (SignalConnectFact, SignalDisconnectFact)

    def check(self, facts: ExtensionFacts, ctx: ExtensionCheckContext) -> None:
        connect_fact = facts.get_fact(SignalConnectFact)
        disconnect_fact = facts.get_fact(SignalDisconnectFact)

        for path, connect_observations in connect_fact.by_path.items():
            if is_prefs_only_context(facts.model, path):
                continue
            disconnect_by_scope = {
                observation.scope_id: observation
                for observation in disconnect_fact.by_path.get(path, [])
            }
            evidences: list[Evidence] = []

            for connect in connect_observations:
                disconnect = disconnect_by_scope.get(connect.scope_id)
                cleaned_signals = {} if disconnect is None else disconnect.signals
                cleaned_signal_groups = (
                    {} if disconnect is None else disconnect.signal_groups
                )

                suppressed_descendants = (
                    owned_descendants(
                        connect.parent_owned,
                        connect.local_parent_owned,
                    )
                    | connect.suppress_root_fields
                )

                parent_owned_signals = {
                    name
                    for name in connect.signals
                    if any(
                        name.startswith(f"anonymous-signal:{child}:")
                        or name.startswith(f"{child}:")
                        for child in suppressed_descendants
                    )
                }
                menu_owned_signals = {
                    name
                    for name in connect.signals
                    if any(
                        name.startswith(f"anonymous-signal:{child}:")
                        or name.startswith(f"{child}:")
                        for child in connect.menu_owned
                    )
                }

                evidences.extend(
                    missing_evidences(
                        connect.signals,
                        cleaned_signals,
                        suppress_names=parent_owned_signals | menu_owned_signals,
                    )
                )
                evidences.extend(
                    missing_evidences(
                        connect.signal_groups,
                        cleaned_signal_groups,
                        suppress_names=set(),
                    )
                )

            if evidences:
                ctx.add_finding(
                    R.EGO_L_003,
                    "Signals assigned in `enable()` are missing matching "
                    "disconnect calls in `disable()` or its helper methods.",
                    evidences,
                )
