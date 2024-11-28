# SPDX-License-Identifer: AGPL-3.0-or-later

import json

from django import template
from django.contrib.staticfiles.storage import (
    ManifestStaticFilesStorage,
    staticfiles_storage,
)
from django.utils.safestring import mark_safe

register = template.Library()
js_paths = None
img_paths = None


@register.simple_tag
@mark_safe
def static_js_paths():
    global js_paths

    if isinstance(staticfiles_storage, ManifestStaticFilesStorage):
        if js_paths is None:
            js_paths = {}

            for base_file, hashed_file in staticfiles_storage.hashed_files.items():
                if base_file.endswith(".js") and base_file.startswith("js/"):
                    js_paths[base_file[3:-3]] = hashed_file[3:-3]

            js_paths = json.dumps(js_paths)

        return js_paths

    return "{}"


@register.simple_tag
@mark_safe
def static_img_paths():
    global img_paths

    if isinstance(staticfiles_storage, ManifestStaticFilesStorage):
        if img_paths is None:
            img_paths = {}

            for base_file, hashed_file in staticfiles_storage.hashed_files.items():
                if base_file.startswith("images/"):
                    img_paths[base_file] = hashed_file

            img_paths = json.dumps(img_paths)

        return img_paths

    return "{}"
