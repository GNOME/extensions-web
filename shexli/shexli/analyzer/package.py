# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import re
import stat
from pathlib import Path
from xml.etree import ElementTree

from ..ast import call_callee_parts, iter_nodes, member_expression_parts, parse_js
from ..models import AnalysisLimits, Evidence, Finding
from ..spec import RULES_BY_ID, R
from .evidence import display_evidence
from .paths import PathMapper
from .safety import read_text_with_limit

UNNECESSARY_PATTERNS = (
    re.compile(r"/?po/"),
    re.compile(r"\.po$"),
    re.compile(r"\.pot$"),
    re.compile(r"(^|/)screenshots(/|$)"),
    re.compile(r"(^|/)(__MACOSX|\.git)(/|$)"),
    re.compile(r"(^|/)\.(gitignore|editorconfig|eslintrc(\.[^.]+)?)$"),
    re.compile(r"(^|/)(build|compile|deploy|install|release)([-_][^/]+)?\.sh$"),
    re.compile(r"(^|/)(Makefile|meson\.build|package-lock\.json|yarn\.lock)$"),
)
LIKELY_BINARY_SUFFIXES = {
    ".so",
    ".dll",
    ".dylib",
    ".a",
    ".o",
    ".pyc",
    ".class",
    ".exe",
    ".bin",
}
PLACEHOLDER_STYLESHEET_TEXTS = {
    "/* Add your custom extension styling here */",
}
KNOWN_SHELL_INTERPRETERS = {
    "ash",
    "bash",
    "csh",
    "dash",
    "fish",
    "ksh",
    "mksh",
    "nu",
    "sh",
    "tcsh",
    "zsh",
}


def metadata_path(root: Path) -> Path:
    return root / "metadata.json"


def _shebang_interpreter(text: str) -> str | None:
    first_line = text.splitlines()[0] if text else ""
    if not first_line.startswith("#!"):
        return None

    parts = first_line[2:].strip().split()
    if not parts:
        return None

    interpreter = Path(parts[0]).name
    if interpreter != "env":
        return interpreter

    # Skip env flags to find the actual command.
    # Flags that consume the next token as their argument:
    _ENV_FLAGS_WITH_VALUE = {"-u", "--unset", "-C", "--chdir"}
    i = 1
    while i < len(parts):
        part = parts[i]
        if part == "--":
            i += 1
            break
        if not part.startswith("-"):
            break
        if part == "-S":
            # -S passes the remainder as a split command line
            i += 1
            break
        if part in _ENV_FLAGS_WITH_VALUE:
            i += 2
        else:
            i += 1

    return Path(parts[i]).name if i < len(parts) else None


def check_package_files(
    files: list[Path],
    findings: list[Finding],
    mapper: PathMapper,
    limits: AnalysisLimits,
    target_versions: set[int] | None = None,
) -> None:
    binary_hits: list[Evidence] = []
    unnecessary_hits: list[Evidence] = []
    compiled_schema_hits: list[Evidence] = []
    script_mismatch_hits: list[Evidence] = []
    target_versions = target_versions or set()

    for path in files:
        rel = mapper.package_path(path)
        suffix = path.suffix.lower()

        if suffix in LIKELY_BINARY_SUFFIXES:
            binary_hits.append(
                display_evidence(path, mapper, snippet="binary-like suffix")
            )
        else:
            try:
                mode = path.stat().st_mode
                if (
                    stat.S_ISREG(mode)
                    and mode & stat.S_IXUSR
                    and suffix not in {".js", ".sh"}
                ):
                    binary_hits.append(
                        display_evidence(
                            path,
                            mapper,
                            snippet="executable file in package",
                        )
                    )
            except OSError:
                pass

        if any(pattern.search(rel) for pattern in UNNECESSARY_PATTERNS):
            unnecessary_hits.append(display_evidence(path, mapper, snippet=rel[:300]))

        if path.name == "gschemas.compiled" and any(
            version >= 45 for version in target_versions
        ):
            compiled_schema_hits.append(
                display_evidence(path, mapper, snippet=rel[:300])
            )

        if path.name == "stylesheet.css":
            try:
                text = read_text_with_limit(path, limits, encoding="utf-8")
            except UnicodeDecodeError:
                text = None

            if text is not None and text.strip() in PLACEHOLDER_STYLESHEET_TEXTS:
                unnecessary_hits.append(
                    display_evidence(
                        path,
                        mapper,
                        snippet="placeholder stylesheet.css",
                    )
                )
        elif suffix == ".sh":
            try:
                text = read_text_with_limit(path, limits, encoding="utf-8")
            except UnicodeDecodeError:
                text = None

            if text is not None:
                interpreter = _shebang_interpreter(text)
                if (
                    interpreter is not None
                    and interpreter not in KNOWN_SHELL_INTERPRETERS
                ):
                    script_mismatch_hits.append(
                        display_evidence(
                            path,
                            mapper,
                            snippet=f"shell-script filename but {interpreter} shebang",
                        )
                    )

    if binary_hits:
        findings.append(
            RULES_BY_ID[R.EGO_P_005].make_finding(
                "Package contains files that look like bundled binaries or libraries.",
                binary_hits[:10],
            )
        )

    if unnecessary_hits:
        findings.append(
            RULES_BY_ID[R.EGO_P_006].make_finding(
                "Package contains files that often should not be shipped for review.",
                unnecessary_hits[:10],
            )
        )

    if compiled_schema_hits:
        findings.append(
            RULES_BY_ID[R.EGO_P_006].make_finding(
                "Compiled GSettings schemas should not be shipped for 45+ packages.",
                compiled_schema_hits[:10],
            )
        )

    if script_mismatch_hits:
        findings.append(
            RULES_BY_ID[R.EGO_P_006].make_finding(
                "Package contains `.sh` scripts with a non-shell shebang.",
                script_mismatch_hits[:10],
            )
        )


def check_schema_files(
    files: list[Path],
    findings: list[Finding],
    mapper: PathMapper,
    limits: AnalysisLimits,
) -> None:
    schema_files = [path for path in files if path.name.endswith(".gschema.xml")]
    if not schema_files:
        return

    for schema_path in schema_files:
        try:
            text = read_text_with_limit(schema_path, limits, encoding="utf-8")
        except UnicodeDecodeError:
            continue

        try:
            xml_root = ElementTree.fromstring(text)
        except ElementTree.ParseError:
            continue

        for schema in xml_root.findall(".//schema"):
            schema_id = schema.attrib.get("id", "")
            schema_file_expected = f"{schema_id}.gschema.xml"
            schema_path_attr = schema.attrib.get("path", "")

            if not schema_id.startswith("org.gnome.shell.extensions"):
                findings.append(
                    RULES_BY_ID[R.EGO_P_001].make_finding(
                        (
                            "GSettings schema id must start with "
                            "`org.gnome.shell.extensions`."
                        ),
                        [
                            display_evidence(
                                schema_path,
                                mapper,
                                snippet=f"id={schema_id!r}",
                            )
                        ],
                    )
                )

            if not schema_path_attr.startswith("/org/gnome/shell/extensions"):
                findings.append(
                    RULES_BY_ID[R.EGO_P_002].make_finding(
                        (
                            "GSettings schema path must start with "
                            "`/org/gnome/shell/extensions`."
                        ),
                        [
                            display_evidence(
                                schema_path,
                                mapper,
                                snippet=f"path={schema_path_attr!r}",
                            )
                        ],
                    )
                )

            if schema_path.name != schema_file_expected:
                findings.append(
                    RULES_BY_ID[R.EGO_P_004].make_finding(
                        (
                            "GSettings schema filename must match "
                            "`<schema-id>.gschema.xml`."
                        ),
                        [
                            display_evidence(
                                schema_path,
                                mapper,
                                snippet=f"expected_filename={schema_file_expected!r}",
                            )
                        ],
                    )
                )


def check_gsettings_usage(
    js_files: list[Path],
    files: list[Path],
    findings: list[Finding],
    limits: AnalysisLimits,
) -> None:
    uses_settings = False
    for path in js_files:
        try:
            text = read_text_with_limit(path, limits, encoding="utf-8")
        except UnicodeDecodeError:
            text = None

        if text is None:
            continue

        tree = parse_js(text)
        for node in iter_nodes(tree.root_node):
            if node.type == "new_expression":
                constructor = node.child_by_field_name("constructor")
                if constructor is not None and member_expression_parts(
                    text, constructor
                ) == ["Gio", "Settings"]:
                    uses_settings = True
                    break
            elif node.type == "call_expression":
                parts = call_callee_parts(text, node)
                if parts and parts[-1] == "getSettings":
                    uses_settings = True
                    break

        if uses_settings:
            break

    if uses_settings and not any(path.name.endswith(".gschema.xml") for path in files):
        findings.append(
            RULES_BY_ID[R.EGO_P_003].make_finding(
                "Extension appears to use GSettings but no "
                "`.gschema.xml` file is included in the package."
            )
        )
