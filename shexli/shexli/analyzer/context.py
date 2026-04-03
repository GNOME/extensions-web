# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..models import Finding
from ..spec import RULES_BY_ID
from .evidence import display_evidence, import_evidence, node_evidence
from .paths import PathMapper


@dataclass(slots=True)
class CheckContext:
    path: Path
    mapper: PathMapper
    findings: list[Finding]

    def add_finding(self, rule_id: str, message: str, evidence=None) -> None:
        self.findings.append(RULES_BY_ID[rule_id].make_finding(message, evidence))

    def display_evidence(self, *, line: int | None = None, snippet: str = ""):
        return display_evidence(self.path, self.mapper, line=line, snippet=snippet)

    def import_evidence(self, item):
        return import_evidence(self.path, self.mapper, item)

    def node_evidence(self, source: str, node):
        return node_evidence(self.path, source, node, self.mapper)
