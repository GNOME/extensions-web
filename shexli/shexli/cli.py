# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter

from .analyzer import analyze_path
from .models import AnalysisResult, Evidence, Finding


def _format_snippet(snippet: str | None) -> str | None:
    if not snippet:
        return None
    stripped = snippet.rstrip("\n")
    return stripped if stripped else None


def _evidence_location(item: Evidence) -> str:
    location = item.path
    if item.line is not None:
        location = f"{location}:{item.line}"
    return location


def _should_render_snippet(item: Evidence, snippet: str | None) -> bool:
    if snippet is None:
        return False
    if item.line is None:
        return False
    return True


def _render_finding(finding: Finding) -> list[str]:
    lines = [f"{finding.rule_id}  {finding.severity}", finding.message, ""]
    if finding.evidence:
        primary = finding.evidence[0]
        location = _evidence_location(primary)
        lines.append(f"  --> {location}")
        snippet = _format_snippet(primary.snippet)
        if _should_render_snippet(primary, snippet):
            lines.append("  |")
            assert snippet is not None
            for snippet_line in snippet.splitlines():
                lines.append(f"  | {snippet_line}")
            lines.append("  |")

    if len(finding.evidence) > 1:
        seen_locations = {_evidence_location(finding.evidence[0])}
        for item in finding.evidence[1:]:
            location = _evidence_location(item)
            if location in seen_locations:
                continue
            seen_locations.add(location)
            if lines[-1] != "":
                lines.append("")
            lines.append(f"  = also: {location}")

    if lines[-1] != "":
        lines.append("")
    lines.append(f"  = rule: {finding.title}")
    if finding.source_url:
        if finding.source_section:
            lines.append(f"  = help: {finding.source_section}")
            lines.append(f"    {finding.source_url}")
        else:
            lines.append(f"  = help: {finding.source_url}")
    return lines


def _write_text(result: AnalysisResult) -> None:
    findings = result.findings
    summary = result.summary
    counts = Counter(finding.severity for finding in findings)

    print(
        f"shexli: {summary['status']} "
        f"({summary['finding_count']} findings, "
        f"{counts.get('error', 0)} errors, {counts.get('warning', 0)} warnings)"
    )
    print()

    for index, finding in enumerate(findings):
        if index:
            print()
        for line in _render_finding(finding):
            print(line)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="shexli",
        description="Static analysis for GNOME Shell extension packages",
    )
    parser.add_argument("path", help="Path to extension directory or ZIP archive")
    parser.add_argument("--format", choices=("json", "text"), default="text")
    args = parser.parse_args()

    result = analyze_path(args.path)
    if args.format == "json":
        json.dump(result.to_dict(), sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    _write_text(result)
    return 0
