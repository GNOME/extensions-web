# ruff: noqa: I001

import os

os.environ.setdefault("EGO_DEBUG", "1")
os.environ.setdefault("EGO_SECRET_KEY", "test-secret-key")
os.environ.setdefault("EGO_CELERY_BROKER_URL", "memory://")

from sweettooth.settings import *  # noqa: F401, F403

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
STATIC_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static"
)
