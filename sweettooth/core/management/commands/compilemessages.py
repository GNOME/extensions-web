# SPDX-License-Identifer: AGPL-3.0-or-later

from pathlib import Path

import polib
from django.core.management.commands.compilemessages import (
    Command as CompileMessagesCommand,
)

from sweettooth.core.management.commands import MessagesCommand


class Command(CompileMessagesCommand, MessagesCommand):
    def handle(self, *args, **options):
        self.check_po_directory()
        self.create_locale_directory()
        self.copy_translations()

        super().handle(*args, **options)

    def copy_translations(self):
        with open(self.linguas_path, "r") as file:
            for line in file:
                lang = line.strip()

                po_path = Path(self.po_path, lang + ".po")
                if not lang or not po_path.is_file():
                    continue

                self.stdout.write("processing language %s\n" % lang)
                source = polib.pofile(po_path)
                django = polib.POFile()
                djangojs = polib.POFile()

                django.metadata = source.metadata
                djangojs.metadata = source.metadata

                for entry in source:
                    for occurrence, line in entry.occurrences:
                        if occurrence.startswith(self.metadata_domain_prefix):
                            domain = occurrence[len(self.metadata_domain_prefix) :]

                            if domain == "django":
                                django.append(entry)
                            elif domain == "djangojs":
                                djangojs.append(entry)

                lang_path = self.locale_path.joinpath(lang, "LC_MESSAGES")
                lang_path.mkdir(parents=True, exist_ok=True)

                django.save(str(lang_path.joinpath("django.po")))
                djangojs.save(str(lang_path.joinpath("djangojs.po")))
