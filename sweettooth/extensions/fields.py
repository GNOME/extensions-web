# SPDX-License-Identifer: AGPL-3.0-or-later

from django.core.validators import URLValidator
from django.db.models import URLField


class HttpURLField(URLField):
    default_validators = [URLValidator(schemes=["http", "https"])]
