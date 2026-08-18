# SPDX-License-Identifer: AGPL-3.0-or-later

import re
from zipfile import BadZipfile
from zlib import error as ZlibError

from django.core.management.base import BaseCommand, CommandError

from sweettooth.extensions.models import ExtensionVersion

DEFAULT_THRESHOLD = 100
DEFAULT_MIN_LENGTH = 200
EXCERPT_LENGTH = 60

# Only these are executed by the Shell, the rest of the archive
# (pixmaps, translations, documentation) is full of aligned text
CODE_EXTENSIONS = (".js",)


class Command(BaseCommand):
    help = (
        "Looks for code hidden behind a long run of whitespace"
        " in the active extension versions."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--threshold",
            type=int,
            default=DEFAULT_THRESHOLD,
            help=(
                "Minimal width of the whitespace run to report the code"
                " behind it, in columns"
                f" (default: {DEFAULT_THRESHOLD})"
            ),
        )
        parser.add_argument(
            "--all-files",
            action="store_true",
            help="Check every text file in the archive, not just the code ones",
        )
        parser.add_argument(
            "--min-length",
            type=int,
            default=DEFAULT_MIN_LENGTH,
            help=(
                "Check the lines longer than this only: a shorter line fits"
                " the screen and hides nothing"
                f" (default: {DEFAULT_MIN_LENGTH})"
            ),
        )

    def _check_version(
        self,
        version: ExtensionVersion,
        pattern: re.Pattern,
        min_length: int,
        threshold: int,
        all_files: bool,
        prefix: str,
    ) -> int:
        found = 0

        with version.get_zipfile("r") as zipfile:
            for info in zipfile.infolist():
                if info.is_dir():
                    continue

                if not all_files and not info.filename.endswith(CODE_EXTENSIONS):
                    continue

                try:
                    content = zipfile.read(info).decode("utf-8")
                except UnicodeDecodeError:
                    # Binary file, nothing to look at
                    continue

                # Only the newline starts a new line here, unlike in
                # splitlines(), so the reported number matches the editor one
                for number, line in enumerate(content.split("\n"), start=1):
                    match = pattern.search(line)
                    if match is None:
                        continue

                    # Tab is 8 columns wide, so expand it to get the widths
                    # the line, the whitespace and the code are displayed at
                    if len(line.expandtabs()) < min_length:
                        continue

                    column = len(line[: match.start(2)].expandtabs()) + 1
                    if column - len(line[: match.start(1)].expandtabs()) < threshold:
                        continue

                    found += 1
                    code = line[match.start(2) :].rstrip("\r")[:EXCERPT_LENGTH]
                    self.stdout.write(
                        f"{prefix} {info.filename}:{number}:{column}: {code}"
                    )

        return found

    def handle(self, *args, **options):
        threshold = options["threshold"]
        if threshold < 1:
            raise CommandError("Threshold must be a positive number")

        min_length = options["min_length"]
        all_files = options["all_files"]

        # A tab counts as 8 columns, so match a shorter run here and check
        # the width it is displayed at later
        pattern = re.compile(r"(\s{%d,})(\S.*)$" % max(threshold // 8, 1))

        versions = ExtensionVersion.objects.visible().order_by("pk")
        total = versions.count()
        self.stdout.write(f"Checking {total} active versions.")

        found = 0
        for version in versions.iterator():
            prefix = f"[{version.pk}][{version.extension.uuid}: {version.version}]"

            try:
                found += self._check_version(
                    version, pattern, min_length, threshold, all_files, prefix
                )
            except OSError as e:
                self.stderr.write(f"{prefix} Unable to find zip file: {str(e)}")
            except BadZipfile:
                self.stderr.write(f"{prefix} Bad zip file: {version.source.name}")
            except ZlibError as e:
                self.stderr.write(f"{prefix} Zlib error: {str(e)}")

            self.stdout.flush()

        self.stdout.write(f"Done, {found} lines found.")
