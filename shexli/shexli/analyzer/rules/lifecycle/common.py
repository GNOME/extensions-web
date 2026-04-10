# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from ...engine import ExtensionModel, JSContext

if TYPE_CHECKING:
    from shexli.models import Evidence

SELF_OWNER = "__self_owner__"


def is_prefs_only_context(model: ExtensionModel, path: Path) -> bool:
    contexts = model.entrypoint_contexts.get(path, set())
    return contexts == {JSContext.PREFERENCES}


def owned_descendants(
    parent_owned: dict[str, str],
    local_parent_owned: dict[str, str],
) -> set[str]:
    roots = {SELF_OWNER}
    descendants: set[str] = set()
    parent_edges = [*parent_owned.items(), *local_parent_owned.items()]

    changed = True
    while changed:
        changed = False
        for child, parent in parent_edges:
            if parent in roots or parent in descendants:
                if child not in descendants:
                    descendants.add(child)
                    changed = True

    return descendants


def missing_evidences(
    created_resources: Mapping[str, Evidence | None],
    cleaned_resources: Mapping[str, Evidence | None],
    suppress_names: set[str] | None = None,
) -> list[Evidence]:
    missing_names = sorted(
        set(created_resources) - set(cleaned_resources) - (suppress_names or set())
    )
    return [e for name in missing_names if (e := created_resources[name]) is not None]


def release_candidates(
    objects: dict[str, Evidence | None],
    resource_refs: dict[str, Evidence | None],
    containers: dict[str, Evidence | None],
    release_container_names: set[str],
) -> dict[str, Evidence]:
    candidates: dict[str, Evidence] = {}
    for resources in (objects, resource_refs):
        for name, evidence in resources.items():
            if evidence is not None:
                candidates.setdefault(name, evidence)

    for name, evidence in containers.items():
        if name in release_container_names and evidence is not None:
            candidates.setdefault(name, evidence)

    return candidates
