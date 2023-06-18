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
    display_name = models.CharField(max_length=150, blank=True)
    last_email_change = models.DateTimeField(blank=True, null=True)
    first_name = None
    last_name = None

    schedule_delete = models.DateTimeField(blank=True, null=True)
    # Yuri Konotopov: this is special permission for me :-)
    # I just want to go through review process regardless of admin status
    force_review = models.BooleanField(default=False)

    def get_full_name(self) -> str:
        return self.display_name or self.username

    def get_short_name(self) -> str:
        return self.get_full_name()
