import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sweettooth.settings")

app = Celery("sweettooth")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
