# SPDX-License-Identifier: AGPL-3.0-or-later

import logging

from shexli.shexli import AnalysisLimits, analyze_path
from sweettooth.extensions.models import ExtensionVersion
from sweettooth.review.models import ShexliResult

logger = logging.getLogger(__name__)

EGO_SHEXLI_LIMITS = AnalysisLimits()


def run_shexli_for_version(
    version: ExtensionVersion,
    *,
    rerun: bool = False,
) -> ShexliResult:
    analysis, _created = ShexliResult.objects.get_or_create(version=version)

    if analysis.result is not None and not rerun:
        return analysis

    try:
        result = analyze_path(
            version.source.path,
            path_mode="embedded",
            limits=EGO_SHEXLI_LIMITS,
        )
    except Exception as exc:
        logger.exception("Shexli failed for version %s", version.pk)
        analysis.error = f"{type(exc).__name__}: {exc}"
        analysis.result = None
    else:
        analysis.error = ""
        analysis.result = result.to_dict()

    analysis.save(update_fields=["error", "result", "updated"])

    return analysis
