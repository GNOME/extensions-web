# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import tempfile
import zipfile
from collections import Counter
from pathlib import Path

from ..models import AnalysisLimits, AnalysisResult, Finding
from ..spec import RULES_BY_ID, SPEC_VERSION, R
from .context import CheckContext
from .evidence import display_evidence
from .js import check_js_file
from .metadata import check_metadata, metadata_target_versions, parse_metadata
from .package import (
    check_gsettings_usage,
    check_package_files,
    check_schema_files,
    metadata_path,
)
from .paths import PathMapper, PathMode
from .reachability import reachable_js_contexts
from .safety import read_text_with_limit, validate_archive, walk_regular_files


def _dedupe_findings(findings: list[Finding]) -> list[Finding]:
    merged: dict[
        tuple[str, str, str, str, str, str],
        Finding,
    ] = {}
    order: list[tuple[str, str, str, str, str, str]] = []

    for finding in findings:
        key = (
            finding.rule_id,
            finding.title,
            finding.severity,
            finding.message,
            finding.source_url,
            finding.source_section,
        )
        if key not in merged:
            merged[key] = Finding(
                rule_id=finding.rule_id,
                title=finding.title,
                severity=finding.severity,
                message=finding.message,
                evidence=[],
                source_url=finding.source_url,
                source_section=finding.source_section,
            )
            order.append(key)

        target = merged[key]
        seen_evidence = {
            (item.path, item.line, item.snippet) for item in target.evidence
        }
        for item in finding.evidence:
            evidence_key = (item.path, item.line, item.snippet)
            if evidence_key in seen_evidence:
                continue

            target.evidence.append(item)
            seen_evidence.add(evidence_key)

    return [merged[key] for key in order]


def analyze_path(
    input_path: str | Path,
    path_mode: PathMode = "cli",
    limits: AnalysisLimits | None = None,
) -> AnalysisResult:
    input_path = Path(input_path)
    limits = limits or AnalysisLimits()
    is_zip = not input_path.is_dir()

    if input_path.is_dir():
        root, tmpdir = input_path, None
    else:
        if not zipfile.is_zipfile(input_path):
            raise ValueError(f"Unsupported input: {input_path}")

        tmpdir = tempfile.TemporaryDirectory(prefix="shexli-")
        try:
            with zipfile.ZipFile(input_path) as archive:
                validate_archive(archive, limits)
                archive.extractall(tmpdir.name)
        except Exception:
            tmpdir.cleanup()
            raise

        root = Path(tmpdir.name)

    try:
        mapper = PathMapper(
            root=root,
            input_path=input_path,
            mode=path_mode,
            is_zip=is_zip,
        )
        findings: list[Finding] = []
        metadata_file = metadata_path(root)

        if not metadata_file.exists():
            findings.append(
                RULES_BY_ID[R.EGO001].make_finding(
                    "Missing required file `metadata.json`."
                )
            )
            metadata = None
        else:
            metadata = parse_metadata(metadata_file, findings, mapper, limits)
            if metadata is not None:
                check_metadata(metadata, metadata_file, findings, mapper)

        target_versions = metadata_target_versions(metadata)
        files = walk_regular_files(root, limits)
        js_files = [path for path in files if path.suffix in {".js", ".mjs"}]
        js_contexts = reachable_js_contexts(root, js_files, limits)
        analyzed_js_files = sorted(js_contexts)
        unreachable_js_files = sorted(set(js_files) - set(analyzed_js_files))

        check_package_files(files, findings, mapper, limits, target_versions)
        check_schema_files(files, findings, mapper, limits)
        check_gsettings_usage(js_files, files, findings, limits)

        if unreachable_js_files:
            findings.append(
                RULES_BY_ID[R.EGO026].make_finding(
                    (
                        "Some JavaScript files are not reachable from "
                        "`extension.js` or `prefs.js` imports."
                    ),
                    [
                        display_evidence(path, mapper)
                        for path in unreachable_js_files[:20]
                    ],
                )
            )

        for path in analyzed_js_files:
            try:
                text = read_text_with_limit(path, limits, encoding="utf-8")
            except UnicodeDecodeError:
                continue

            ctx = CheckContext(path, mapper, findings)
            check_js_file(
                ctx,
                text,
                metadata,
                target_versions,
                js_contexts[path],
            )

        findings = _dedupe_findings(findings)
        severity_counts = Counter(finding.severity for finding in findings)
        summary = {
            "input_path": str(input_path),
            "finding_count": len(findings),
            "severity_counts": dict(severity_counts),
            "status": "clean" if not findings else "issues_found",
        }
        artifacts = {
            "root": mapper.display_root(),
            "metadata_path": (
                mapper.display_path(metadata_file) if metadata_file.exists() else None
            ),
            "js_file_count": len(analyzed_js_files),
            "file_count": len(files),
            "limits": {
                "max_files": limits.max_files,
                "max_file_size_bytes": limits.max_file_size_bytes,
                "max_total_file_bytes": limits.max_total_file_bytes,
                "max_zip_members": limits.max_zip_members,
                "max_zip_uncompressed_bytes": limits.max_zip_uncompressed_bytes,
                "max_zip_compression_ratio": limits.max_zip_compression_ratio,
            },
            "target_versions": sorted(target_versions),
        }

        return AnalysisResult(
            spec_version=SPEC_VERSION,
            summary=summary,
            findings=findings,
            artifacts=artifacts,
        )
    finally:
        if tmpdir is not None:
            tmpdir.cleanup()
