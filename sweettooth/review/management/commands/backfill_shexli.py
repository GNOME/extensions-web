# SPDX-License-Identifier: AGPL-3.0-or-later

from django.core.management.base import BaseCommand
from django.db.models import Q

from sweettooth.extensions.models import ExtensionVersion
from sweettooth.review.shexli import run_shexli_for_version


class Command(BaseCommand):
    help = "Run Shexli for unreviewed versions without a successful Shexli result."

    def add_arguments(self, parser):
        parser.add_argument(
            "--rerun",
            action="store_true",
            help="Rerun Shexli for all unreviewed versions, even if a result exists.",
        )

    def handle(self, *args, **options):
        versions = ExtensionVersion.objects.unreviewed()
        rerun = options["rerun"]

        if not rerun:
            versions = versions.filter(
                Q(shexli_result__isnull=True) | Q(shexli_result__result__isnull=True)
            )

        versions = versions.order_by("pk")

        total = versions.count()
        if rerun:
            self.stdout.write(f"Found {total} unreviewed versions to rerun.")
        else:
            self.stdout.write(f"Found {total} versions without Shexli results.")

        for index, version in enumerate(versions.iterator(), start=1):
            analysis = run_shexli_for_version(version, rerun=rerun)
            self.stdout.write(
                f"[{index}/{total}] version={version.pk} "
                f"{'failed' if analysis.error else 'ok'}"
            )
