# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

from ..models import AnalysisLimits, Evidence, Finding
from ..spec import RULES_BY_ID
from .paths import PathMapper
from .safety import read_text_with_limit

UUID_ALLOWED_RE = re.compile(r"[-a-zA-Z0-9@._]+$")
DONATION_ALLOWED_KEYS = {
    "buymeacoffee",
    "custom",
    "github",
    "kofi",
    "liberapay",
    "opencollective",
    "patreon",
    "paypal",
}


class InvalidShellVersion(Exception):
    pass


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
            minor = prerelease_versions.get(minor)
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
    if at <= 0:
        return False

    return True


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
    findings: list[Finding],
    mapper: PathMapper,
    limits: AnalysisLimits,
) -> dict | None:
    try:
        text = read_text_with_limit(metadata_path, limits, encoding="utf-8")
    except UnicodeDecodeError:
        findings.append(
            RULES_BY_ID["EGO002"].make_finding(
                "`metadata.json` is not valid UTF-8 text.",
                [
                    _metadata_evidence(
                        metadata_path,
                        mapper,
                        "Unable to decode file as UTF-8.",
                    )
                ],
            )
        )
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        findings.append(
            RULES_BY_ID["EGO002"].make_finding(
                f"`metadata.json` is invalid JSON: {exc.msg}.",
                [
                    _metadata_evidence(
                        metadata_path,
                        mapper,
                        (exc.doc.splitlines()[exc.lineno - 1] if exc.lineno else "")[
                            :300
                        ],
                        line=exc.lineno,
                    )
                ],
            )
        )
        return None


def _check_uuid(
    metadata: dict,
    metadata_path: Path,
    findings: list[Finding],
    mapper: PathMapper,
) -> None:
    uuid = metadata.get("uuid")
    if not isinstance(uuid, str) or not validate_uuid(uuid):
        findings.append(
            RULES_BY_ID["EGO003"].make_finding(
                (
                    "Field `uuid` must match EGO UUID constraints and must "
                    "not end with `gnome.org` or a subdomain of it."
                ),
                [_metadata_evidence(metadata_path, mapper, f"uuid={uuid!r}")],
            )
        )


def _check_shell_versions(
    metadata: dict,
    metadata_path: Path,
    findings: list[Finding],
    mapper: PathMapper,
) -> None:
    shell_versions = metadata.get("shell-version")
    if not isinstance(shell_versions, list) or not shell_versions:
        findings.append(
            RULES_BY_ID["EGO004"].make_finding(
                (
                    "Field `shell-version` must be a non-empty list of "
                    "supported GNOME Shell versions."
                ),
                [
                    _metadata_evidence(
                        metadata_path,
                        mapper,
                        f"shell-version={shell_versions!r}",
                    )
                ],
            )
        )
        return

    invalid: list[str] = []
    dev_count = 0
    future: list[str] = []

    for raw in shell_versions:
        if not isinstance(raw, str):
            invalid.append(str(raw))
            continue

        try:
            major, minor, _point = parse_version_string(raw)
        except InvalidShellVersion:
            invalid.append(raw)
            continue

        if major >= 40 and minor < -1:
            dev_count += 1

        if major > 50:
            future.append(raw)

    if invalid or dev_count > 1 or future:
        findings.append(
            RULES_BY_ID["EGO004"].make_finding(
                (
                    "Field `shell-version` contains invalid values, "
                    "more than one development release, or implausible "
                    "future releases."
                ),
                [
                    _metadata_evidence(
                        metadata_path,
                        mapper,
                        f"shell-version={shell_versions!r}",
                    )
                ],
            )
        )


def _check_session_modes(
    metadata: dict,
    metadata_path: Path,
    findings: list[Finding],
    mapper: PathMapper,
) -> None:
    session_modes = metadata.get("session-modes")
    if session_modes is None:
        return

    allowed = {"user", "unlock-dialog"}

    if not isinstance(session_modes, list) or any(
        mode not in allowed for mode in session_modes
    ):
        findings.append(
            RULES_BY_ID["EGO006"].make_finding(
                (
                    "Field `session-modes` may only contain `user` and "
                    "`unlock-dialog`."
                ),
                [
                    _metadata_evidence(
                        metadata_path,
                        mapper,
                        f"session-modes={session_modes!r}",
                    )
                ],
            )
        )
    elif set(session_modes) == {"user"}:
        findings.append(
            RULES_BY_ID["EGO005"].make_finding(
                (
                    "Field `session-modes` should be omitted when it "
                    "only contains `user`."
                ),
                [
                    _metadata_evidence(
                        metadata_path,
                        mapper,
                        f"session-modes={session_modes!r}",
                    )
                ],
            )
        )


def _check_donations(
    metadata: dict,
    metadata_path: Path,
    findings: list[Finding],
    mapper: PathMapper,
) -> None:
    donations = metadata.get("donations")
    if donations is None:
        return

    if not isinstance(donations, dict):
        findings.append(
            RULES_BY_ID["EGO007"].make_finding(
                (
                    "Field `donations` must be an object keyed by supported "
                    "donation provider names."
                ),
                [_metadata_evidence(metadata_path, mapper, f"donations={donations!r}")],
            )
        )
        return

    unknown = [key for key in donations if key not in DONATION_ALLOWED_KEYS]
    if unknown:
        findings.append(
            RULES_BY_ID["EGO007"].make_finding(
                "Field `donations` contains unsupported donation types.",
                [
                    _metadata_evidence(
                        metadata_path,
                        mapper,
                        f"unknown_keys={unknown!r}",
                    )
                ],
            )
        )

    for key, values in donations.items():
        normalized = values if isinstance(values, list) else [values]

        if not normalized:
            findings.append(
                RULES_BY_ID["EGO007"].make_finding(
                    f"Donation type `{key}` must contain at least one value.",
                    [_metadata_evidence(metadata_path, mapper, f"{key}={values!r}")],
                )
            )
            continue

        if len(normalized) > 3:
            findings.append(
                RULES_BY_ID["EGO007"].make_finding(
                    f"Donation type `{key}` must not contain more than 3 values.",
                    [_metadata_evidence(metadata_path, mapper, f"{key}={values!r}")],
                )
            )

        if any(not isinstance(value, str) for value in normalized):
            findings.append(
                RULES_BY_ID["EGO007"].make_finding(
                    f"Donation type `{key}` must be a string or a list of strings.",
                    [_metadata_evidence(metadata_path, mapper, f"{key}={values!r}")],
                )
            )
            continue

        if key != "custom":
            continue

        for value in normalized:
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                findings.append(
                    RULES_BY_ID["EGO007"].make_finding(
                        "Custom donation URLs must use `http` or `https`.",
                        [
                            _metadata_evidence(
                                metadata_path,
                                mapper,
                                f"custom={value!r}",
                            )
                        ],
                    )
                )


def check_metadata(
    metadata: dict,
    metadata_path: Path,
    findings: list[Finding],
    mapper: PathMapper,
) -> None:
    _check_uuid(metadata, metadata_path, findings, mapper)
    _check_shell_versions(metadata, metadata_path, findings, mapper)
    _check_session_modes(metadata, metadata_path, findings, mapper)
    _check_donations(metadata, metadata_path, findings, mapper)


def metadata_target_versions(metadata: dict | None) -> set[int]:
    if not metadata:
        return set()

    targets: set[int] = set()
    shell_versions = metadata.get("shell-version")
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
