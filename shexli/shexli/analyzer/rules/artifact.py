# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import re

from ...spec import R
from ..facts.extension import (
    ExtensionArtifactFact,
    GSettingsUsageFact,
)
from .api import (
    ExtensionCheckContext,
    ExtensionFacts,
    ExtensionRule,
)

_UNNECESSARY_PATH_PATTERNS = (
    re.compile(r"/?po/"),
    re.compile(r"\.po$"),
    re.compile(r"\.pot$"),
    re.compile(r"(^|/)screenshots(/|$)"),
    re.compile(r"(^|/)(__MACOSX|\.git)(/|$)"),
    re.compile(r"(^|/)\.(gitignore|editorconfig|eslintrc(\.[^.]+)?)$"),
    re.compile(r"(^|/)(build|compile|deploy|install|release)([-_][^/]+)?\.sh$"),
    re.compile(r"(^|/)(Makefile|meson\.build|package-lock\.json|yarn\.lock)$"),
)


class ExtensionArtifactRule(ExtensionRule):
    """ExtensionRule: package-file, schema, and GSettings artifact checks."""

    required_extension_facts = (ExtensionArtifactFact, GSettingsUsageFact)

    def check(self, facts: ExtensionFacts, ctx: ExtensionCheckContext) -> None:
        artifact_fact = facts.get_fact(ExtensionArtifactFact)
        gsettings_usage = facts.get_fact(GSettingsUsageFact)
        package_files = facts.model.package_files
        file_observations = {
            observation.path: observation
            for observation in artifact_fact.file_observations
        }

        binary_evidences = [
            observation.evidence
            for observation in artifact_fact.file_observations
            if observation.binary_hint is not None
        ]
        compiled_schema_evidences = [
            ctx.display_evidence(
                package_file.path,
                snippet=package_file.package_path[:300],
            )
            for package_file in package_files
            if (
                package_file.path.name == "gschemas.compiled"
                and any(version >= 45 for version in facts.model.target_versions)
            )
        ]
        unnecessary_evidences = []
        for package_file in package_files:
            observation = file_observations.get(package_file.path)
            if any(
                pattern.search(package_file.package_path)
                for pattern in _UNNECESSARY_PATH_PATTERNS
            ):
                unnecessary_evidences.append(
                    ctx.display_evidence(
                        package_file.path,
                        snippet=package_file.package_path[:300],
                    )
                )
            elif observation is not None and observation.is_placeholder_stylesheet:
                unnecessary_evidences.append(observation.evidence)
        script_mismatch_evidences = [
            observation.evidence
            for observation in artifact_fact.file_observations
            if observation.shebang_interpreter is not None
        ]

        if binary_evidences:
            ctx.add_finding(
                R.EGO_P_005,
                "Package contains files that look like bundled binaries or libraries.",
                binary_evidences[:10],
            )

        unnecessary = unnecessary_evidences[:10]
        if unnecessary:
            ctx.add_finding(
                R.EGO_P_006,
                "Package contains files that often should not be shipped for review.",
                unnecessary,
            )

        if compiled_schema_evidences:
            ctx.add_finding(
                R.EGO_P_006,
                "Compiled GSettings schemas should not be shipped for 45+ packages.",
                compiled_schema_evidences[:10],
            )

        if script_mismatch_evidences:
            ctx.add_finding(
                R.EGO_P_006,
                "Package contains `.sh` scripts with a non-shell shebang.",
                script_mismatch_evidences[:10],
            )

        for observation in artifact_fact.schema_observations:
            if not observation.schema_id.startswith("org.gnome.shell.extensions"):
                ctx.add_finding(
                    R.EGO_P_001,
                    "GSettings schema id must start with `org.gnome.shell.extensions`.",
                    [observation.evidence],
                )
            if not observation.schema_path.startswith("/org/gnome/shell/extensions"):
                ctx.add_finding(
                    R.EGO_P_002,
                    (
                        "GSettings schema path must start with "
                        "`/org/gnome/shell/extensions`."
                    ),
                    [observation.evidence],
                )
            if observation.filename != observation.expected_filename:
                ctx.add_finding(
                    R.EGO_P_004,
                    "GSettings schema filename must match `<schema-id>.gschema.xml`.",
                    [observation.evidence],
                )

        if gsettings_usage.uses_gsettings and not any(
            package_file.path.name.endswith(".gschema.xml")
            for package_file in package_files
        ):
            ctx.add_finding(
                R.EGO_P_003,
                (
                    "Extension appears to use GSettings but no "
                    "`.gschema.xml` file is included in the package."
                ),
            )

        if facts.model.unreachable_js_files:
            ctx.add_finding(
                R.EGO_P_007,
                (
                    "Some JavaScript files are not reachable from "
                    "`extension.js` or `prefs.js` imports."
                ),
                [
                    ctx.display_evidence(path)
                    for path in facts.model.unreachable_js_files[:20]
                ],
            )
