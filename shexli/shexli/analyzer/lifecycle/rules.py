# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass

from ...models import Evidence, Finding
from ...spec import RULES_BY_ID


@dataclass(frozen=True, slots=True)
class LifecycleRuleSpec:
    rule_id: str
    created_attr: str
    cleaned_attr: str
    message: str


LIFECYCLE_RULES = (
    LifecycleRuleSpec(
        rule_id="EGO015",
        created_attr="signals",
        cleaned_attr="signals",
        message=(
            "Signals assigned in `enable()` are missing matching disconnect "
            "calls in `disable()` or its helper methods."
        ),
    ),
    LifecycleRuleSpec(
        rule_id="EGO015",
        created_attr="signal_groups",
        cleaned_attr="signal_groups",
        message=(
            "Signal handler collections created in `enable()` are missing "
            "matching disconnect loops in `disable()` or its helper methods."
        ),
    ),
    LifecycleRuleSpec(
        rule_id="EGO016",
        created_attr="sources",
        cleaned_attr="sources",
        message=(
            "Main loop sources assigned in `enable()` are missing matching "
            "removals in `disable()` or its helper methods."
        ),
    ),
    LifecycleRuleSpec(
        rule_id="EGO016",
        created_attr="source_groups",
        cleaned_attr="source_groups",
        message=(
            "Main loop source collections created in `enable()` are missing "
            "matching removal loops in `disable()` or its helper methods."
        ),
    ),
    LifecycleRuleSpec(
        rule_id="EGO014",
        created_attr="objects",
        cleaned_attr="objects",
        message=(
            "Objects assigned in `enable()` are missing matching `.destroy()` "
            "calls in `disable()` or its helper methods."
        ),
    ),
    LifecycleRuleSpec(
        rule_id="EGO014",
        created_attr="object_groups",
        cleaned_attr="object_groups",
        message=(
            "Object collections created in `enable()` are missing matching "
            "destroy loops in `disable()` or its helper methods."
        ),
    ),
)


def _append_missing_lifecycle_findings(
    findings: list[Finding],
    created_resources: dict[str, Evidence | None],
    cleaned_resources: dict[str, Evidence | None],
    rule_id: str,
    message: str,
    suppress_names: set[str] | None = None,
) -> None:
    missing_names = sorted(
        set(created_resources) - set(cleaned_resources) - (suppress_names or set())
    )
    if not missing_names:
        return

    findings.append(
        RULES_BY_ID[rule_id].make_finding(
            message,
            [created_resources[name] for name in missing_names],
        )
    )


def _release_candidates(
    created,
    release_container_names: set[str],
) -> dict[str, Evidence]:
    candidates: dict[str, Evidence] = {}
    for resources in (created.objects, created.resource_refs):
        for name, evidence in resources.items():
            if evidence is not None:
                candidates.setdefault(name, evidence)

    for name, evidence in created.containers.items():
        if name in release_container_names and evidence is not None:
            candidates.setdefault(name, evidence)

    return candidates


def append_lifecycle_findings(
    findings: list[Finding],
    created,
    cleaned,
    include_object_cleanup: bool = True,
    release_container_names: set[str] | None = None,
) -> None:
    release_container_names = release_container_names or set()
    parent_owned_children = {
        child
        for child, parent in created.parent_owned.items()
        if parent in created.objects or parent in created.resource_refs
    }
    local_parent_owned_children = {
        child
        for child, parent in created.local_parent_owned.items()
        if (
            parent in created.objects
            or parent in created.resource_refs
            or parent in parent_owned_children
        )
    }
    parent_owned_signals = {
        name
        for name in created.signals
        if any(
            name.startswith(f"anonymous-signal:{child}:")
            for child in (parent_owned_children | local_parent_owned_children)
        )
    }
    menu_owned_signals = {
        name
        for name in created.signals
        if any(
            name.startswith(f"anonymous-signal:{child}:")
            for child in created.menu_owned
        )
    }
    for rule in LIFECYCLE_RULES:
        if not include_object_cleanup and rule.rule_id == "EGO014":
            continue

        if rule.created_attr == "signals":
            suppress_names = parent_owned_signals | menu_owned_signals
        elif rule.rule_id == "EGO014":
            suppress_names = parent_owned_children
        else:
            suppress_names = set()

        _append_missing_lifecycle_findings(
            findings,
            getattr(created, rule.created_attr),
            getattr(cleaned, rule.cleaned_attr),
            rule.rule_id,
            rule.message,
            suppress_names=suppress_names,
        )

    if created.recreated_sources:
        findings.append(
            RULES_BY_ID["EGO035"].make_finding(
                (
                    "Main loop sources should be removed before creating a "
                    "new source on the same field."
                ),
                list(created.recreated_sources.values()),
            )
        )

    if include_object_cleanup:
        _append_missing_lifecycle_findings(
            findings,
            _release_candidates(created, release_container_names),
            cleaned.released_refs,
            "EGO027",
            (
                "Owned references that are cleaned up in `disable()` should "
                "also be released with `null` or `undefined`."
            ),
            suppress_names=parent_owned_children - release_container_names,
        )
