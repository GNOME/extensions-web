"""
Django settings for sweettooth project.

For the full list of settings and their values, see
https://docs.djangoproject.com/en/stable/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import datetime
import os
from urllib.parse import urljoin

import dj_database_url
from captcha import constants as captcha_constants
from django.utils.log import DEFAULT_LOGGING as LOGGING

SITE_ROOT = os.path.dirname(os.path.abspath(__file__))

BASE_DIR = os.path.dirname(SITE_ROOT)

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/stable/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# Set this in local_settings.py to some random value
SECRET_KEY = os.getenv("EGO_SECRET_KEY") or ""

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True if os.getenv("EGO_DEBUG") else False

ALLOWED_HOSTS = [os.getenv("EGO_ALLOWED_HOST") or "extensions.gnome.org"]

# Application definition

INSTALLED_APPS = [
    "django.contrib.auth",
    "django_registration",
    "maintenance_mode",
    # 'ratings' goes before django's comments
    # app so it will find our templates
    "sweettooth.ratings",
    "captcha",
    "django_comments",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.staticfiles",
    "django.contrib.messages",
    "rest_framework",
    "django_filters",
    "knox",
    "rest_registration",
    "django_opensearch_dsl",
    "sweettooth.extensions",
    "sweettooth.auth",
    "sweettooth.core",
    "sweettooth.review",
    "sweettooth.templates",
    "sweettooth.users",
    "django.contrib.admin",
    "drf_spectacular",
    "drf_spectacular_sidecar",
]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "maintenance_mode.middleware.MaintenanceModeMiddleware",
]

if "EGO_CORS_ORIGINS" in os.environ:
    MIDDLEWARE.insert(0, "corsheaders.middleware.CorsMiddleware")
    INSTALLED_APPS.append("corsheaders")
    CORS_ORIGIN_WHITELIST = list(
        map(str.strip, os.environ["EGO_CORS_ORIGINS"].split(","))
    )

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "users.User"
AUTHENTICATION_BACKENDS = ["sweettooth.auth.backends.LoginEmailAuthentication"]

MAINTAINER_WANTED_USERNAME = "MaintainerWanted"
# Disallow authentication and registration when
# username contains words. Case insensitive.
DISALLOWED_USERNAMES = (
    "admin",
    "GNOME",
    "official",
    MAINTAINER_WANTED_USERNAME,
)

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

TOKEN_TTL_DAYS = 3
REST_KNOX = {
    "TOKEN_TTL": datetime.timedelta(days=TOKEN_TTL_DAYS),
    "TOKEN_LIMIT_PER_USER": TOKEN_TTL_DAYS * 15,
    "AUTO_REFRESH": True,
}

BASE_URL = os.getenv("EGO_BASE_URL", "https://extensions.gnome.org")

ROOT_URLCONF = "sweettooth.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(SITE_ROOT, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.request",
                "sweettooth.review.context_processors.n_unreviewed_extensions",
                "sweettooth.auth.context_processors.login_form",
                "sweettooth.context_processors.navigation",
            ],
            "debug": DEBUG,
        },
    },
]

WSGI_APPLICATION = "sweettooth.wsgi.application"


# Database
# https://docs.djangoproject.com/en/stable/ref/settings/#databases
DATABASES = {
    "default": dj_database_url.config(
        env="EGO_DATABASE_URL", default="sqlite://./test.db"
    )
}

OPENSEARCH_DSL = {
    "default": {"hosts": os.getenv("EGO_OPENSEARCH_ADDRESS") or "localhost:9200"},
}

OPENSEARCH_DSL_AUTOSYNC = True

# Internationalization
# https://docs.djangoproject.com/en/stable/topics/i18n/

LANGUAGE_CODE = "en-us"
LOCALE_PATHS = [os.path.join(SITE_ROOT, "locale")]

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = False

ADMINS = (
    (
        os.getenv("EGO_ADMINISTRATOR_NAME") or "Administrator",
        os.getenv("EGO_ADMINISTRATOR_EMAIL") or "admin@localhost.local",
    ),
)

MANAGERS = ADMINS

SITE_ID = 1

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = os.getenv("EGO_MEDIA_ROOT") or os.path.join(
    SITE_ROOT, "..", "uploaded-files"
)

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = "/extension-data/"

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/stable/howto/static-files/

STATIC_URL = "/static/"

STATICFILES_DIRS = (os.path.join(SITE_ROOT, "static"),)

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    },
}

DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("EGO_MAX_UPLOAD", 5 * 1024 * 1024))
FILE_UPLOAD_MAX_MEMORY_SIZE = DATA_UPLOAD_MAX_MEMORY_SIZE

ACCOUNT_ACTIVATION_DAYS = 5

LOGIN_URL = "/accounts/login/"

COMMENTS_APP = "sweettooth.ratings"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("knox.auth.TokenAuthentication",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "PAGE_SIZE": 10,
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "GNOME Extensions",
    "DESCRIPTION": "extensions.gnome.org",
    "VERSION": "1",
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATION_PARAMETERS": False,
    "SERVE_INCLUDE_SCHEMA": False,
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
}

RECAPTCHA_PUBLIC_KEY = os.getenv(
    "EGO_RECAPTCHA_PUBLIC_KEY", captcha_constants.TEST_PUBLIC_KEY
)
RECAPTCHA_PRIVATE_KEY = os.getenv(
    "EGO_RECAPTCHA_PRIVATE_KEY", captcha_constants.TEST_PRIVATE_KEY
)
SILENCED_SYSTEM_CHECKS = ["captcha.recaptcha_test_key_error"]

# See http://docs.djangoproject.com/en/stable/topics/logging for
# more details on how to customize your logging configuration.

LOGGING["filters"]["require_not_maintenance_mode_503"] = {
    "()": "maintenance_mode.logging.RequireNotMaintenanceMode503",
}
LOGGING["handlers"]["mail_admins"]["filters"].append("require_not_maintenance_mode_503")

LOGGING["handlers"]["console"]["filters"] = None
LOGGING["handlers"]["console"]["level"] = "DEBUG"

LOGGING["loggers"] = {
    "django": {
        "handlers": ["console", "mail_admins"],
        "level": os.getenv("EGO_LOG_LEVEL", "WARN"),
    }
}


DEFAULT_FROM_EMAIL = "noreply@gnome.org"
SERVER_EMAIL = DEFAULT_FROM_EMAIL
if os.getenv("EGO_EMAIL_URL"):
    import dj_email_url

    vars().update(dj_email_url.parse(os.getenv("EGO_EMAIL_URL")))


NO_SECURE_SETTINGS = True if os.getenv("EGO_NO_SECURE_SETTINGS") else False
NO_STATICFILES_SETTINGS = False

REST_REGISTRATION = {
    "REGISTER_EMAIL_VERIFICATION_URL": urljoin(BASE_URL, "/verify-email"),
    "REGISTER_VERIFICATION_URL": urljoin(BASE_URL, "/verify-user"),
    "RESET_PASSWORD_VERIFICATION_URL": urljoin(BASE_URL, "/reset-password"),
    "VERIFICATION_FROM_EMAIL": DEFAULT_FROM_EMAIL,
    "USER_LOGIN_FIELDS": ("username",),
    "REGISTER_SERIALIZER_CLASS": "sweettooth.auth.serializers.RegisterUserSerializer",
    "REGISTER_VERIFICATION_PERIOD": datetime.timedelta(days=5),
    "REGISTER_VERIFICATION_ONE_TIME_USE": True,
    "REGISTER_VERIFICATION_AUTO_LOGIN": True,
    "AUTH_TOKEN_MANAGER_CLASS": "sweettooth.auth.authentication.KnoxAuthTokenManager",
    "LOGIN_RETRIEVE_TOKEN": True,
}

MAINTENANCE_MODE_STATE_BACKEND = "maintenance_mode.backends.DefaultStorageBackend"
MAINTENANCE_MODE_STATE_FILE_NAME = ".ego_maintenance_enabled.txt"
MAINTENANCE_MODE_IGNORE_ADMIN_SITE = True
MAINTENANCE_MODE_TEMPLATE = "maintenance.html"
MAINTENANCE_MODE_STATUS_CODE = 503
MAINTENANCE_MODE_RETRY_AFTER = 60

try:
    from local_settings import *  # noqa: F401, F403
except ImportError:
    pass

# Enable secure settings in case DEBUG is disabled and
# NO_SECURE_SETTINGS is not set to True
if not DEBUG and not NO_SECURE_SETTINGS:
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 4 * 60 * 60
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_PROXY_SSL_HEADER = ("HTTPS", "https")
    SECURE_SSL_REDIRECT = False

if "EGO_STATIC_ROOT" in os.environ:
    STATIC_ROOT = os.getenv("EGO_STATIC_ROOT")
elif DEBUG and not NO_STATICFILES_SETTINGS:
    STORAGES["staticfiles"]["BACKEND"] = (
        "django.contrib.staticfiles.storage.StaticFilesStorage"
    )
    STATIC_ROOT = None
