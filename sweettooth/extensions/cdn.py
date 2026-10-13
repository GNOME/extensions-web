# SPDX-License-Identifer: AGPL-3.0-or-later

import json
import urllib.request

from django.conf import settings
from django.db import transaction


def purge(*files):
    paths = [file.url for file in files if file]
    if not paths or not settings.CDN77_TOKEN:
        return

    def send():
        request = urllib.request.Request(
            f"https://api.cdn77.com/v3/cdn/{settings.CDN77_CDN_ID}/job/purge",
            data=json.dumps({"paths": paths}).encode(),
            method="POST",
            headers={
                "Authorization": f"Bearer {settings.CDN77_TOKEN}",
                "Content-Type": "application/json",
            },
        )
        urllib.request.urlopen(request, timeout=5).close()

    transaction.on_commit(send, robust=True)
