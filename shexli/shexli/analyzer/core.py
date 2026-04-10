# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import stat
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, cast

from ..ast import parse_js
from ..models import AnalysisLimits, AnalysisResult, Finding
from ..spec import RULES, SPEC_VERSION
from .engine import (
    ExtensionModel,
    JSContext,
    PackageFile,
    PathMapper,
    PathMode,
)
from .evidence import display_evidence, import_evidence, node_evidence
from .facts import EXTENSION_FACT_BUILDERS, FILE_FACT_BUILDERS, FactStore
from .file import JSFileModelBuilder
from .lifecycle.cross_file import build_cross_file_indices_per_file
from .metadata import metadata_target_versions, parse_metadata
from .reachability import reachable_js_contexts
from .rules import EXTENSION_RULES, JS_FILE_RULES
from .rules.api import (
    ExtensionCheckContext,
    ExtensionFacts,
    JSFileCheckContext,
    JSFileFacts,
)
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


def _check_js_file(
    ctx: JSFileCheckContext,
    facts: JSFileFacts,
    fact_store: FactStore,
    target_versions: set[int],
    contexts: set[JSContext],
) -> None:
    ctx.target_versions = target_versions
    ctx.contexts = contexts

    for rule in JS_FILE_RULES:
        if rule.applies(ctx):
            for fact_type in rule.required_file_facts:
                fact_store.get_file_fact(facts.model.path, fact_type)
            rule.check(facts, ctx)


def _build_package_files(
    files: list[Path],
    mapper: PathMapper,
) -> list[PackageFile]:
    package_files: list[PackageFile] = []
    for path in files:
        try:
            mode = path.stat().st_mode
        except OSError:
            is_executable = False
        else:
            is_executable = stat.S_ISREG(mode) and bool(mode & stat.S_IXUSR)
        package_files.append(
            PackageFile(
                path=path,
                package_path=mapper.package_path(path),
                suffix=path.suffix.lower(),
                is_executable=is_executable,
            )
        )
    return package_files


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
        metadata = parse_metadata(
            root / ExtensionModel.METADATA_PACKAGE_PATH, mapper, limits
        )
        target_versions = metadata_target_versions(metadata)
        files = walk_regular_files(root, limits)
        package_files = _build_package_files(files, mapper)
        js_files = [path for path in files if path.suffix in {".js", ".mjs"}]
        js_contexts = reachable_js_contexts(root, js_files, limits)
        analyzed_js_files = sorted(js_contexts)
        unreachable_js_files = sorted(set(js_files) - set(analyzed_js_files))

        file_models = {}
        for path in analyzed_js_files:
            try:
                text = read_text_with_limit(path, limits, encoding="utf-8")
            except UnicodeDecodeError:
                continue

            root_node = parse_js(text).root_node
            file_models[path] = JSFileModelBuilder().build(
                path, text, root_node, mapper
            )

        extension_model = ExtensionModel(
            cross_file_index=build_cross_file_indices_per_file(sorted(file_models)),
            root_dir=root,
            metadata=metadata,
            target_versions=target_versions,
            js_file_count=len(file_models),
            entrypoint_contexts=js_contexts,
            unreachable_js_files=unreachable_js_files,
            package_files=package_files,
            all_files=files,
            js_files=js_files,
            limits=limits,
            mapper=mapper,
            files=file_models,
        )
        fact_store = FactStore(
            extension_model,
            file_fact_builders=FILE_FACT_BUILDERS,
            extension_fact_builders=EXTENSION_FACT_BUILDERS,
        )

        for path in sorted(file_models):
            ctx = JSFileCheckContext(
                path=path,
                make_finding=lambda rule_id, message, evidence=None: RULES[
                    rule_id
                ].make_finding(message, evidence),
                add_finding=findings.append,
                display_evidence=lambda *, line=None, snippet="", path=path: (
                    display_evidence(path, mapper, line=line, snippet=snippet)
                ),
                import_evidence=lambda item, path=path: import_evidence(
                    path, mapper, item
                ),
                node_evidence=lambda source, node, path=path: node_evidence(
                    path,
                    source,
                    cast(Any, node),
                    mapper,
                ),
            )
            file_facts = JSFileFacts(
                file_models[path],
                lambda fact_type, path=path, fact_store=fact_store: (
                    fact_store.get_file_fact(path, fact_type)
                ),
            )
            _check_js_file(
                ctx,
                file_facts,
                fact_store,
                target_versions,
                js_contexts[path],
            )

        extension_ctx = ExtensionCheckContext(
            make_finding=lambda rule_id, message, evidence=None: RULES[
                rule_id
            ].make_finding(message, evidence),
            add_finding=findings.append,
            display_evidence=lambda path, mapper=mapper: (
                lambda *, line=None, snippet="": display_evidence(
                    path, mapper, line=line, snippet=snippet
                )
            ),
        )
        extension_facts = ExtensionFacts(
            extension_model,
            lambda fact_type, fact_store=fact_store: fact_store.get_extension_fact(
                fact_type
            ),
        )
        for rule in EXTENSION_RULES:
            if rule.applies(extension_model):
                for fact_type in rule.required_extension_facts:
                    fact_store.get_extension_fact(fact_type)
                rule.check(extension_facts, extension_ctx)

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
                mapper.display_path(metadata.path) if metadata.exists else None
            ),
            "js_file_count": len(file_models),
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
