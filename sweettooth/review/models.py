from django.conf import settings
from django.db import models

from sweettooth.extensions.models import STATUSES, ExtensionVersion


class CodeReview(models.Model):
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL
    )
    date = models.DateTimeField(auto_now_add=True)
    comments = models.TextField(blank=True)
    version = models.ForeignKey(
        ExtensionVersion, on_delete=models.CASCADE, related_name="reviews"
    )
    new_status = models.PositiveIntegerField(choices=STATUSES.items(), null=True)
    auto = models.BooleanField(default=False)

    class Meta:
        permissions = (
            ("can-review-extensions", "Can review extensions"),
            ("trusted", "Trusted author"),
        )


class ShexliResult(models.Model):
    version = models.OneToOneField(
        ExtensionVersion,
        on_delete=models.CASCADE,
        related_name="shexli_result",
    )
    result = models.JSONField(blank=True, null=True)
    error = models.TextField(blank=True)
    updated = models.DateTimeField(auto_now=True)
