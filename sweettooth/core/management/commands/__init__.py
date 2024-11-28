# SPDX-License-Identifer: AGPL-3.0-or-later

from pathlib import Path

from django.conf import settings


class MessagesCommand:
    metadata_domain_prefix = "extensions-web-domain-"
    po_path = Path(settings.BASE_DIR).joinpath("po")
    linguas_path = Path(po_path).joinpath("LINGUAS")
    locale_path = Path(settings.SITE_ROOT).joinpath("locale")

    def check_po_directory(self):
        Path(self.po_path).mkdir(parents=True, exist_ok=True)
        Path(self.linguas_path).touch(exist_ok=True)

    def create_locale_directory(self):
        self.locale_path.mkdir(parents=True, exist_ok=True)
