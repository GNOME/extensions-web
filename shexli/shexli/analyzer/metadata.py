# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from ..models import AnalysisLimits, Evidence
from .engine import PathMapper
from .safety import read_text_with_limit


class InvalidShellVersion(Exception):
    pass


UUID_ALLOWED_RE = re.compile(r"[-a-zA-Z0-9@._]+$")
KNOWN_METADATA_FIELDS = frozenset(
    {
        "description",
        "donations",
        "gettext-domain",
        "name",
        "session-modes",
        "settings-schema",
        "shell-version",
        "url",
        "uuid",
        "version",
    }
)


@dataclass(frozen=True, slots=True)
class MetadataParseFailure:
    kind: Literal["utf8", "json", "shape"]
    evidence: Evidence
    details: str | None = None


@dataclass(frozen=True, slots=True)
class Metadata:
    path: Path
    exists: bool
    raw_json: dict[str, object] | None = None
    parse_failure: MetadataParseFailure | None = None
    unknown_fields: dict[str, object] = field(default_factory=dict)

    @classmethod
    def missing(cls, path: Path) -> Metadata:
        return cls(path=path, exists=False)

    @property
    def is_valid(self) -> bool:
        return self.exists and self.parse_failure is None and self.raw_json is not None

    @property
    def uuid(self) -> str | None:
        value = self.get("uuid")
        return value if isinstance(value, str) else None

    @property
    def shell_versions(self) -> list[object] | None:
        value = self.get("shell-version")
        return value if isinstance(value, list) else None

    @property
    def session_modes(self) -> list[object] | None:
        value = self.get("session-modes")
        return value if isinstance(value, list) else None

    @property
    def donations(self) -> dict[str, object] | None:
        value = self.get("donations")
        return value if isinstance(value, dict) else None

    def get(self, key: str, default: object | None = None) -> object | None:
        if self.raw_json is None:
            return default
        return self.raw_json.get(key, default)


def parse_version_string(version_string: str) -> tuple[int, int, int]:
    prerelease_versions = {
        "alpha": -4,
        "beta": -3,
        "rc": -2,
    }
    version = version_string.split(".")
    version_parts = len(version)

    if version_parts < 1 or version_parts > 3:
        raise InvalidShellVersion()

    try:
        major = int(version[0])
        minor = version[1] if version_parts > 1 else -1
        if major >= 40 and minor in prerelease_versions:
            minor = prerelease_versions[minor]
        else:
            minor = int(minor)
    except ValueError as exc:
        raise InvalidShellVersion() from exc

    point = -1
    if version_parts > 2:
        if major < 40:
            try:
                point = int(version[2])
            except ValueError as exc:
                raise InvalidShellVersion() from exc
    else:
        if major < 40 and (version_parts < 2 or minor % 2 != 0):
            raise InvalidShellVersion()

    return major, minor, point


def validate_uuid(uuid: str) -> bool:
    if UUID_ALLOWED_RE.match(uuid) is None:
        return False

    if re.search(r"[.@]gnome\.org$", uuid) is not None:
        return False

    at = uuid.find("@")
    return at > 0


def _metadata_evidence(
    metadata_path: Path,
    mapper: PathMapper,
    snippet: str,
    line: int | None = None,
) -> Evidence:
    return Evidence(
        path=mapper.display_path(metadata_path),
        line=line,
        snippet=snippet,
    )


def parse_metadata(
    metadata_path: Path,
    mapper: PathMapper,
    limits: AnalysisLimits,
) -> Metadata:
    """Read and parse ``metadata.json`` into a coherent metadata object."""
    if not metadata_path.exists():
        return Metadata.missing(metadata_path)

    try:
        text = read_text_with_limit(metadata_path, limits, encoding="utf-8")
    except UnicodeDecodeError:
        return Metadata(
            path=metadata_path,
            exists=True,
            parse_failure=MetadataParseFailure(
                kind="utf8",
                evidence=_metadata_evidence(
                    metadata_path,
                    mapper,
                    "Unable to decode file as UTF-8.",
                ),
            ),
        )

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return Metadata(
            path=metadata_path,
            exists=True,
            parse_failure=MetadataParseFailure(
                kind="json",
                details=exc.msg,
                evidence=_metadata_evidence(
                    metadata_path,
                    mapper,
                    (exc.doc.splitlines()[exc.lineno - 1] if exc.lineno else "")[:300],
                    line=exc.lineno,
                ),
            ),
        )

    if not isinstance(data, dict):
        type_name = type(data).__name__
        return Metadata(
            path=metadata_path,
            exists=True,
            parse_failure=MetadataParseFailure(
                kind="shape",
                details="top-level JSON value must be an object, got " + type_name,
                evidence=_metadata_evidence(
                    metadata_path,
                    mapper,
                    (text.splitlines()[0] if text else "")[:300],
                    line=1 if text else None,
                ),
            ),
        )

    return Metadata(
        path=metadata_path,
        exists=True,
        raw_json=data,
        unknown_fields={
            key: value
            for key, value in data.items()
            if key not in KNOWN_METADATA_FIELDS
        },
    )


def metadata_target_versions(metadata: Metadata) -> set[int]:
    if not metadata.is_valid:
        return set()

    targets: set[int] = set()
    shell_versions = metadata.shell_versions
    if not isinstance(shell_versions, list):
        return targets

    for raw in shell_versions:
        if not isinstance(raw, str):
            continue

        try:
            major, _minor, _point = parse_version_string(raw)
        except InvalidShellVersion:
            continue

        if major >= 40:
            targets.add(major)

    return targets
