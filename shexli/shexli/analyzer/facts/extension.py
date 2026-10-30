# SPDX-License-Identifier: AGPL-3.0-or-later

"""Extension-level facts built from file-level analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from xml.etree import ElementTree

from ...ast import (
    call_callee_parts,
    iter_nodes,
    member_expression_parts,
    parse_js,
)
from ..evidence import display_evidence
from ..evidence import node_evidence as _node_evidence
from ..safety import read_text_with_limit
from .base import ExtensionFactBuilder, ExtensionFactContext
from .file import PrefsFact, SessionModesFact

if TYPE_CHECKING:
    from ...models import Evidence


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
    env_flags_with_value = {"-u", "--unset", "-C", "--chdir"}
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
        if part in env_flags_with_value:
            i += 2
        else:
            i += 1

    return Path(parts[i]).name if i < len(parts) else None


@dataclass(frozen=True, slots=True)
class PreferencesMethodObservation:
    """Observed preferences API method and its evidence.

    Attributes:
        name: Method name observed on the exported preferences object/class.
        evidence: Evidence pointing at the method declaration.
    """

    name: str
    evidence: Evidence


@dataclass(frozen=True, slots=True)
class PreferencesStateAssignmentObservation:
    """Observed assignment retained on the exported preferences object.

    Attributes:
        field_name: Assigned field name on the exported preferences object.
        value_kind: AST node type of the assigned value expression.
        evidence: Evidence pointing at the assignment.
    """

    field_name: str
    value_kind: str
    evidence: Evidence


@dataclass(frozen=True, slots=True)
class PreferencesCleanupObservation:
    """Observed cleanup behavior for retained preferences state.

    Attributes:
        signal_name: Signal used to trigger cleanup.
        evidence: Evidence pointing at the cleanup hookup.
    """

    signal_name: str
    evidence: Evidence


@dataclass(frozen=True, slots=True)
class PrefsExtensionFact:
    """Extension-level preferences observations aggregated from `prefs.js`.

    Attributes:
        method_observations: Preferences methods observed on the exported
            preferences class or object.
        state_assignment_observations: Assignments that retain state on the
            exported preferences object.
        cleanup_observations: Cleanup observations tied to retained state.
    """

    method_observations: list[PreferencesMethodObservation] = field(
        default_factory=list
    )
    state_assignment_observations: list[PreferencesStateAssignmentObservation] = field(
        default_factory=list
    )
    cleanup_observations: list[PreferencesCleanupObservation] = field(
        default_factory=list
    )


@dataclass(frozen=True, slots=True)
class DisableMethodObservation:
    """Observed `disable()` method and any attached documentation comment.

    Attributes:
        method_evidence: Evidence pointing at the `disable()` method.
        comment_evidence: Evidence for a nearby explanatory comment, if any.
    """

    method_evidence: Evidence
    comment_evidence: Evidence | None = None


@dataclass(frozen=True, slots=True)
class SessionModesExtensionFact:
    """Session-modes observations aggregated from the extension entrypoint.

    Attributes:
        disable_observation: `disable()` observation from `extension.js`, if
            the entrypoint is analyzed and declares the method.
    """

    disable_observation: DisableMethodObservation | None = None


@dataclass(frozen=True, slots=True)
class ArtifactFileObservation:
    """General file-level hints reused by package artifact rules.

    Attributes:
        path: Absolute package file path.
        evidence: Source or display evidence for the file.
        binary_hint: Human-readable binary/file-type heuristic, if any.
        shebang_interpreter: Parsed interpreter name for `.sh` files, when
            present.
        is_placeholder_stylesheet: Whether `stylesheet.css` matches a known
            placeholder template.
    """

    path: Path
    evidence: Evidence
    binary_hint: str | None = None
    shebang_interpreter: str | None = None
    is_placeholder_stylesheet: bool = False


@dataclass(frozen=True, slots=True)
class SchemaObservation:
    """Observed schema metadata extracted from a `.gschema.xml` file.

    Attributes:
        evidence: Evidence pointing at the schema declaration.
        filename: Filename containing the schema declaration.
        schema_id: Parsed schema ID attribute.
        schema_path: Parsed schema path attribute.
        expected_filename: Conventional filename derived from `schema_id`.
    """

    evidence: Evidence
    filename: str
    schema_id: str
    schema_path: str
    expected_filename: str


@dataclass(frozen=True, slots=True)
class ExtensionArtifactFact:
    """General package/schema observations for artifact-related rules.

    Attributes:
        file_observations: File-level heuristics such as binary-like suffixes,
            placeholder stylesheets, or shebang mismatches.
        schema_observations: Parsed GSettings schema metadata from XML files.
    """

    file_observations: list[ArtifactFileObservation] = field(default_factory=list)
    schema_observations: list[SchemaObservation] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class GSettingsUsageFact:
    """Whether analyzed JS code appears to instantiate or look up GSettings.

    Attributes:
        uses_gsettings: Whether any analyzed JS file appears to create
            `Gio.Settings` instances or call `getSettings()`.
    """

    uses_gsettings: bool = False


class PrefsExtensionFactBuilder(ExtensionFactBuilder[PrefsExtensionFact]):
    """Build extension-level preferences observations."""

    fact_type = PrefsExtensionFact

    def build(self, ctx: ExtensionFactContext) -> PrefsExtensionFact:
        """Aggregate preferences observations from the analyzed `prefs.js`."""
        package_file = ctx.extension.package_file(
            ctx.extension.PREFERENCES_ENTRYPOINT_PACKAGE_PATH
        )
        path = (
            package_file.path
            if package_file is not None and package_file.path in ctx.extension.files
            else None
        )
        if path is None:
            return PrefsExtensionFact()

        prefs_fact = ctx.get_file_fact(path, PrefsFact)
        file_model = ctx.extension.files[path]

        method_observations = [
            PreferencesMethodObservation(
                name="getPreferencesWidget",
                evidence=_node_evidence(path, file_model.text, node, file_model.mapper),
            )
            for node in prefs_fact.get_preferences_widget_nodes
        ]
        state_assignment_observations = [
            PreferencesStateAssignmentObservation(
                field_name=(
                    member_expression_parts(
                        file_model.text,
                        left,
                    )[-1]
                    if (left := node.child_by_field_name("left")) is not None
                    else ""
                ),
                value_kind=(
                    right.type
                    if (right := node.child_by_field_name("right")) is not None
                    else ""
                ),
                evidence=_node_evidence(
                    path,
                    file_model.text,
                    node,
                    file_model.mapper,
                ),
            )
            for node in prefs_fact.state_assignment_nodes
        ]
        cleanup_observations = [
            PreferencesCleanupObservation(
                signal_name="close-request",
                evidence=_node_evidence(
                    path,
                    file_model.text,
                    node,
                    file_model.mapper,
                ),
            )
            for node in prefs_fact.close_request_cleanup_nodes
        ]
        return PrefsExtensionFact(
            method_observations=method_observations,
            state_assignment_observations=state_assignment_observations,
            cleanup_observations=cleanup_observations,
        )


class SessionModesExtensionFactBuilder(ExtensionFactBuilder[SessionModesExtensionFact]):
    """Build extension-level session-modes observations."""

    fact_type = SessionModesExtensionFact

    def build(self, ctx: ExtensionFactContext) -> SessionModesExtensionFact:
        """Aggregate `disable()` observations from the analyzed entrypoint."""
        package_file = ctx.extension.package_file(
            ctx.extension.EXTENSION_ENTRYPOINT_PACKAGE_PATH
        )
        path = (
            package_file.path
            if package_file is not None and package_file.path in ctx.extension.files
            else None
        )
        if path is None:
            return SessionModesExtensionFact()

        session_modes_fact = ctx.get_file_fact(path, SessionModesFact)
        file_model = ctx.extension.files[path]
        disable_observation = None

        if session_modes_fact.disable_method_nodes:
            method_evidence = _node_evidence(
                path,
                file_model.text,
                session_modes_fact.disable_method_nodes[0],
                file_model.mapper,
            )
            comment_evidence = None
            if session_modes_fact.commented_disable_nodes:
                comment_evidence = _node_evidence(
                    path,
                    file_model.text,
                    session_modes_fact.commented_disable_nodes[0],
                    file_model.mapper,
                )
            disable_observation = DisableMethodObservation(
                method_evidence=method_evidence,
                comment_evidence=comment_evidence,
            )

        return SessionModesExtensionFact(disable_observation=disable_observation)


def _collect_schema_observations(
    ctx: ExtensionFactContext,
    schema_files: list[Path],
) -> list[SchemaObservation]:
    observations: list[SchemaObservation] = []
    for schema_path in schema_files:
        try:
            text = read_text_with_limit(
                schema_path, ctx.extension.limits, encoding="utf-8"
            )
        except UnicodeDecodeError:
            continue

        try:
            xml_root = ElementTree.fromstring(text)
        except ElementTree.ParseError:
            continue

        for schema in xml_root.findall(".//schema"):
            schema_id = schema.attrib.get("id", "")
            schema_path_attr = schema.attrib.get("path", "")
            expected_filename = f"{schema_id}.gschema.xml"
            observations.append(
                SchemaObservation(
                    evidence=display_evidence(
                        schema_path,
                        ctx.extension.mapper,
                        snippet=f"id={schema_id!r} path={schema_path_attr!r}",
                    ),
                    filename=schema_path.name,
                    schema_id=schema_id,
                    schema_path=schema_path_attr,
                    expected_filename=expected_filename,
                )
            )
    return observations


def _extension_uses_gsettings(ctx: ExtensionFactContext) -> bool:
    for path in ctx.extension.js_files:
        try:
            text = read_text_with_limit(path, ctx.extension.limits, encoding="utf-8")
        except UnicodeDecodeError:
            continue

        tree = parse_js(text)
        for node in iter_nodes(tree.root_node):
            if node.type == "new_expression":
                constructor = node.child_by_field_name("constructor")
                if constructor is not None and member_expression_parts(
                    text, constructor
                ) == ["Gio", "Settings"]:
                    return True
            elif node.type == "call_expression":
                parts = call_callee_parts(text, node)
                if parts and parts[-1] == "getSettings":
                    return True

    return False


class ExtensionArtifactFactBuilder(ExtensionFactBuilder[ExtensionArtifactFact]):
    """Build extension-level package-file and schema observations."""

    fact_type = ExtensionArtifactFact

    def build(self, ctx: ExtensionFactContext) -> ExtensionArtifactFact:
        """Build general package-file and schema observations."""
        file_observations: list[ArtifactFileObservation] = []
        schema_files = [
            package_file.path
            for package_file in ctx.extension.package_files
            if package_file.path.name.endswith(".gschema.xml")
        ]

        for package_file in ctx.extension.package_files:
            path = package_file.path
            if package_file.suffix in LIKELY_BINARY_SUFFIXES:
                file_observations.append(
                    ArtifactFileObservation(
                        path=path,
                        evidence=display_evidence(
                            path, ctx.extension.mapper, snippet="binary-like suffix"
                        ),
                        binary_hint="binary-like suffix",
                    )
                )
            elif package_file.is_executable and package_file.suffix not in {
                ".js",
                ".sh",
            }:
                file_observations.append(
                    ArtifactFileObservation(
                        path=path,
                        evidence=display_evidence(
                            path,
                            ctx.extension.mapper,
                            snippet="executable file in package",
                        ),
                        binary_hint="executable file in package",
                    )
                )

            if path.name == "stylesheet.css":
                try:
                    text = read_text_with_limit(
                        path, ctx.extension.limits, encoding="utf-8"
                    )
                except UnicodeDecodeError:
                    text = None

                if text is not None and text.strip() in PLACEHOLDER_STYLESHEET_TEXTS:
                    file_observations.append(
                        ArtifactFileObservation(
                            path=path,
                            evidence=display_evidence(
                                path,
                                ctx.extension.mapper,
                                snippet="placeholder stylesheet.css",
                            ),
                            is_placeholder_stylesheet=True,
                        )
                    )
            elif package_file.suffix == ".sh":
                try:
                    text = read_text_with_limit(
                        path, ctx.extension.limits, encoding="utf-8"
                    )
                except UnicodeDecodeError:
                    text = None

                if text is not None:
                    interpreter = _shebang_interpreter(text)
                    if (
                        interpreter is not None
                        and interpreter not in KNOWN_SHELL_INTERPRETERS
                    ):
                        file_observations.append(
                            ArtifactFileObservation(
                                path=path,
                                evidence=display_evidence(
                                    path,
                                    ctx.extension.mapper,
                                    snippet=(
                                        f"shell-script filename but {interpreter} "
                                        "shebang"
                                    ),
                                ),
                                shebang_interpreter=interpreter,
                            )
                        )

        return ExtensionArtifactFact(
            file_observations=file_observations,
            schema_observations=_collect_schema_observations(ctx, schema_files),
        )


class GSettingsUsageFactBuilder(ExtensionFactBuilder[GSettingsUsageFact]):
    """Build extension-level GSettings usage observations."""

    fact_type = GSettingsUsageFact

    def build(self, ctx: ExtensionFactContext) -> GSettingsUsageFact:
        """Detect whether analyzed JS code appears to use GSettings."""
        return GSettingsUsageFact(uses_gsettings=_extension_uses_gsettings(ctx))
