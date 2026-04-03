# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class RuleSpec:
    rule_id: str
    title: str
    severity: str
    source_url: str
    source_section: str
    static_checkable: bool
    detection_strategy: str
    rationale: str

    def make_finding(
        self,
        message: str,
        evidence: list[Evidence] | None = None,
    ) -> Finding:
        return Finding(
            rule_id=self.rule_id,
            title=self.title,
            severity=self.severity,
            message=message,
            evidence=evidence or [],
            source_url=self.source_url,
            source_section=self.source_section,
        )


@dataclass(slots=True)
class Evidence:
    path: str
    line: int | None = None
    snippet: str | None = None


@dataclass(slots=True)
class Finding:
    rule_id: str
    title: str
    severity: str
    message: str
    evidence: list[Evidence] = field(default_factory=list)
    source_url: str = ""
    source_section: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence"] = [asdict(item) for item in self.evidence]
        return payload


@dataclass(slots=True)
class AnalysisResult:
    spec_version: str
    summary: dict[str, Any]
    findings: list[Finding]
    artifacts: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec_version": self.spec_version,
            "summary": self.summary,
            "findings": [finding.to_dict() for finding in self.findings],
            "artifacts": self.artifacts,
        }


@dataclass(slots=True, frozen=True)
class AnalysisLimits:
    max_files: int = 5_000
    max_file_size_bytes: int = 10 * 1024 * 1024
    max_total_file_bytes: int = 50 * 1024 * 1024
    max_zip_members: int = 5_000
    max_zip_uncompressed_bytes: int = 50 * 1024 * 1024
    max_zip_compression_ratio: int = 1_000
