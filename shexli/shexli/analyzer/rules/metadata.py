# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import re
from urllib.parse import urlparse

from ...spec import R
from .api import (
    ExtensionCheckContext,
    ExtensionFacts,
    ExtensionRule,
)


class MetadataValidationRule(ExtensionRule):
    """ExtensionRule: EGO_M_001/M_002 bootstrap + semantic metadata validation."""

    def check(self, facts: ExtensionFacts, ctx: ExtensionCheckContext) -> None:
        metadata = facts.model.metadata
        if not metadata.exists:
            ctx.add_finding(R.EGO_M_001, "Missing required file `metadata.json`.")
            return

        if metadata.parse_failure is not None:
            err = metadata.parse_failure
            if err.kind == "utf8":
                message = "`metadata.json` is not valid UTF-8 text."
            elif err.kind == "json":
                detail = f": {err.details}" if err.details else "."
                message = f"`metadata.json` is invalid JSON{detail}"
            else:
                detail = f": {err.details}" if err.details else "."
                prefix = "`metadata.json` must contain a top-level JSON object"
                message = prefix + detail
            ctx.add_finding(R.EGO_M_002, message, [err.evidence])
            return

        if not metadata.is_valid:
            return
        metadata_file = metadata.path

        raw_uuid = metadata.get("uuid")
        uuid = metadata.uuid
        if uuid is None or not _validate_uuid(uuid):
            ctx.add_finding(
                R.EGO_M_003,
                (
                    "Field `uuid` must match EGO UUID constraints and must "
                    "not end with `gnome.org` or a subdomain of it."
                ),
                [ctx.display_evidence(metadata_file, snippet=f"uuid={raw_uuid!r}")],
            )

        raw_shell_versions = metadata.get("shell-version")
        shell_versions = metadata.shell_versions
        if shell_versions is None or not shell_versions:
            ctx.add_finding(
                R.EGO_M_004,
                (
                    "Field `shell-version` must be a non-empty list of "
                    "supported GNOME Shell versions."
                ),
                [
                    ctx.display_evidence(
                        metadata_file,
                        snippet=f"shell-version={raw_shell_versions!r}",
                    )
                ],
            )
        else:
            invalid: list[str] = []
            dev_count = 0
            future: list[str] = []
            for raw in shell_versions:
                if not isinstance(raw, str):
                    invalid.append(str(raw))
                    continue
                parsed = _parse_version_string(raw)
                if parsed is None:
                    invalid.append(raw)
                    continue
                major, minor, _point = parsed
                if major >= 40 and minor < -1:
                    dev_count += 1
                if major > 50:
                    future.append(raw)
            if invalid or dev_count > 1 or future:
                ctx.add_finding(
                    R.EGO_M_004,
                    (
                        "Field `shell-version` contains invalid values, "
                        "more than one development release, or implausible "
                        "future releases."
                    ),
                    [
                        ctx.display_evidence(
                            metadata_file,
                            snippet=f"shell-version={raw_shell_versions!r}",
                        )
                    ],
                )

        raw_session_modes = metadata.get("session-modes")
        session_modes = metadata.session_modes
        if raw_session_modes is not None:
            allowed = {"user", "unlock-dialog"}
            if session_modes is None or any(
                mode not in allowed for mode in session_modes
            ):
                ctx.add_finding(
                    R.EGO_M_006,
                    (
                        "Field `session-modes` may only contain `user` "
                        "and `unlock-dialog`."
                    ),
                    [
                        ctx.display_evidence(
                            metadata_file,
                            snippet=f"session-modes={raw_session_modes!r}",
                        )
                    ],
                )
            elif set(session_modes) == {"user"}:
                ctx.add_finding(
                    R.EGO_M_005,
                    (
                        "Field `session-modes` should be omitted when "
                        "it only contains `user`."
                    ),
                    [
                        ctx.display_evidence(
                            metadata_file,
                            snippet=f"session-modes={raw_session_modes!r}",
                        )
                    ],
                )

        raw_donations = metadata.get("donations")
        donations = metadata.donations
        if raw_donations is None:
            return

        if donations is None:
            ctx.add_finding(
                R.EGO_M_007,
                (
                    "Field `donations` must be an object keyed by supported "
                    "donation provider names."
                ),
                [
                    ctx.display_evidence(
                        metadata_file, snippet=f"donations={raw_donations!r}"
                    )
                ],
            )
            return

        unknown = [key for key in donations if key not in _DONATION_ALLOWED_KEYS]
        if unknown:
            ctx.add_finding(
                R.EGO_M_007,
                "Field `donations` contains unsupported donation types.",
                [
                    ctx.display_evidence(
                        metadata_file,
                        snippet=f"unknown_keys={unknown!r}",
                    )
                ],
            )

        for key, values in donations.items():
            normalized = values if isinstance(values, list) else [values]
            if not normalized:
                ctx.add_finding(
                    R.EGO_M_007,
                    f"Donation type `{key}` must contain at least one value.",
                    [ctx.display_evidence(metadata_file, snippet=f"{key}={values!r}")],
                )
                continue
            if len(normalized) > 3:
                ctx.add_finding(
                    R.EGO_M_007,
                    f"Donation type `{key}` must not contain more than 3 values.",
                    [ctx.display_evidence(metadata_file, snippet=f"{key}={values!r}")],
                )
            if any(not isinstance(value, str) for value in normalized):
                ctx.add_finding(
                    R.EGO_M_007,
                    f"Donation type `{key}` must be a string or a list of strings.",
                    [ctx.display_evidence(metadata_file, snippet=f"{key}={values!r}")],
                )
                continue
            if key != "custom":
                continue
            for value in normalized:
                assert isinstance(value, str)
                parsed = urlparse(value)
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    ctx.add_finding(
                        R.EGO_M_007,
                        "Custom donation URLs must use `http` or `https`.",
                        [
                            ctx.display_evidence(
                                metadata_file, snippet=f"custom={value!r}"
                            )
                        ],
                    )


_UUID_ALLOWED_RE = re.compile(r"[-a-zA-Z0-9@._]+$")
_DONATION_ALLOWED_KEYS = {
    "buymeacoffee",
    "custom",
    "github",
    "kofi",
    "liberapay",
    "opencollective",
    "patreon",
    "paypal",
}


def _parse_version_string(version_string: str) -> tuple[int, int, int] | None:
    prerelease_versions = {"alpha": -4, "beta": -3, "rc": -2}
    version = version_string.split(".")
    if len(version) < 1 or len(version) > 3:
        return None
    try:
        major = int(version[0])
        minor = version[1] if len(version) > 1 else -1
        if major >= 40 and minor in prerelease_versions:
            minor = prerelease_versions[minor]
        else:
            minor = int(minor)
    except ValueError:
        return None
    point = -1
    if len(version) > 2:
        if major < 40:
            try:
                point = int(version[2])
            except ValueError:
                return None
    elif major < 40 and (len(version) < 2 or minor % 2 != 0):
        return None
    return major, minor, point


def _validate_uuid(uuid: str) -> bool:
    if _UUID_ALLOWED_RE.match(uuid) is None:
        return False
    if re.search(r"[.@]gnome\.org$", uuid) is not None:
        return False
    at = uuid.find("@")
    return at > 0
