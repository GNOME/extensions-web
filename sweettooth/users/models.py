# SPDX-License-Identifer: AGPL-3.0-or-later

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
