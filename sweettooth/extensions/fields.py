"""
    GNOME Shell Extensions Repository
    Copyright (C) 2021 Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""

from django.core.validators import URLValidator
from django.db.models import URLField


class HttpURLField(URLField):
    default_validators = [URLValidator(schemes=["http", "https"])]
