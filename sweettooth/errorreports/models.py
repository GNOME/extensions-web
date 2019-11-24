
from django.conf import settings
from django.db import models
from django.dispatch import Signal
from sweettooth.extensions.models import Extension

class ErrorReport(models.Model):
    comment = models.TextField(blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    extension = models.ForeignKey(Extension, null=True, on_delete=models.CASCADE)

error_reported = Signal(providing_args=["request", "version", "report"])
