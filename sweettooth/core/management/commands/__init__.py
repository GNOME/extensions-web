"""
    GNOME Shell extensions repository
    Copyright (C) 2019  Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""

from django.conf import settings
from pathlib import Path

class MessagesCommand:
    metadata_domain_prefix = 'extensions-web-domain-'
    po_path = Path(settings.BASE_DIR).joinpath('po')
    linguas_path = Path(po_path).joinpath('LINGUAS')
    locale_path = Path(settings.SITE_ROOT).joinpath("locale")

    def check_po_directory(self):
        Path(self.po_path).mkdir(parents=True, exist_ok=True)
        Path(self.linguas_path).touch(exist_ok=True)

    def create_locale_directory(self):
        self.locale_path.mkdir(parents=True, exist_ok=True)
