"""
    GNOME Shell extensions repository
    Copyright (C) 2022  Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    schedule_delete = models.DateTimeField(blank=True, null=True)
