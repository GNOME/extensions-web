
from django.contrib import auth
from django.db import models
from django.dispatch import Signal
from sweettooth.extensions.models import Extension

class ErrorReport(models.Model):
    comment = models.TextField(blank=True)
    user = models.ForeignKey(auth.models.User, related_name="+")
    extension = models.ForeignKey(Extension, null=True)

error_reported = Signal(providing_args=["request", "version", "report"])
