# SPDX-License-Identifer: AGPL-3.0-or-later

from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

import polib
import pytz
from django.conf import settings
from django.core.management.commands.makemessages import Command as MakeMessagesCommand

from sweettooth.core.management.commands import MessagesCommand


class GettextParser(HTMLParser):
    in_gettext = False
    po = None
    file = None

    def __init__(self, po):
        super().__init__(convert_charrefs=True)
        self.po = po

    def set_file(self, file):
        self.file = file

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "x-gettext":
            self.in_gettext = True
        else:
            self.in_gettext = False

    def handle_endtag(self, tag):
        self.in_gettext = False

    def handle_data(self, data):
        if self.in_gettext:
            (line, offset) = self.getpos()
            self.po.append(polib.POEntry(msgid=data, occurrences=[(self.file, line)]))


class Command(MakeMessagesCommand, MessagesCommand):
    def handle(self, *args, **options):
        options["keep_pot"] = True

        self.check_po_directory()
        self.create_locale_directory()

        for domain in ("django", "djangojs"):
            self.locale_paths = []
            options["domain"] = domain
            super().handle(*args, **options)

        self.create_po_template()

        for domain in ("django", "djangojs"):
            self.domain = domain
            self.remove_potfiles()

    def build_potfiles(self):
        potfiles = super().build_potfiles()
        if self.domain == "djangojs":
            if len(set(potfiles)) > 1:
                # We do not support multiple locale dirs
                raise NotImplementedError("Multiple locale dirs are not supported")

            po = polib.pofile(potfiles[0], check_for_duplicates=True)

            self.search_mustache_texts(po)

            po.sort()
            po.save(potfiles[0])

        return potfiles

    def search_mustache_texts(self, po):
        extensions = self.extensions
        self.extensions = {".mst"}

        parser = GettextParser(po)
        file_list = self.find_files(Path(settings.SITE_ROOT).joinpath("static", "js"))
        for translatable_file in file_list:
            with open(translatable_file.path, "r") as file:
                parser.set_file(
                    translatable_file.path.replace(settings.BASE_DIR, "").lstrip("/")
                )
                parser.feed(file.read())
                parser.reset()

        self.extensions = extensions

    def create_po_template(self):
        django = polib.pofile(
            str(Path(self.locale_paths[0]).joinpath("django.pot")),
            check_for_duplicates=True,
        )
        djangojs = polib.pofile(
            str(Path(self.locale_paths[0]).joinpath("djangojs.pot")),
            check_for_duplicates=True,
        )

        self.add_po_domain(django, "django")
        self.add_po_domain(djangojs, "djangojs")

        for entry in djangojs:
            django.append(entry)

        django.header = "\nGNOME Shell extensions repository\n"
        django.header += "\n"
        django.header += "DO NOT EDIT!\n"
        django.header += "This file is auto generated with manage.py makemessages."
        django.header += "\n"

        django.metadata = {
            "Project-Id-Version": "1.0",
            "Report-Msgid-Bugs-To": "ykonotopov@gnome.org",
            "POT-Creation-Date": datetime.now(pytz.utc).strftime("%Y-%m-%d %H:%M%z"),
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=utf-8",
            "Content-Transfer-Encoding": "8bit",
        }
        django.sort()
        django.save(Path(self.po_path).joinpath("extensions-web.pot"))

    def add_po_domain(self, po, domain):
        for entry in po:
            entry.occurrences.append((self.metadata_domain_prefix + domain, 1))
