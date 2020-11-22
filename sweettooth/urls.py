from django.conf import settings
from django.conf.urls import include
from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, re_path
from django.views import static
from django.views.generic.base import TemplateView
from django.views.i18n import JavaScriptCatalog

admin.autodiscover()

urlpatterns = [
    path("api/", include("sweettooth.api.v1.urls")),
    # 'login' and 'register'
    re_path(r"^accounts/", include("sweettooth.auth.urls")),
    re_path(r"^", include("sweettooth.extensions.urls"), name="index"),
    re_path(r"^review/", include("sweettooth.review.urls")),
    re_path(r"^jsi18n/$", JavaScriptCatalog.as_view(), name="javascript-catalog"),
    re_path(r"^admin/", admin.site.urls),
    re_path(r"^comments/", include("sweettooth.ratings.urls")),
    re_path(r"^comments/", include("django_comments.urls")),
    re_path(
        r"^robots\.txt$",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
    ),
]

if settings.DEBUG:
    # Use static.serve for development...
    urlpatterns.append(
        re_path(
            r"^extension-data/(?P<path>.*)",
            static.serve,
            dict(document_root=settings.MEDIA_ROOT),
            name="extension-data",
        )
    )
else:
    # and a dummy to reverse on for production.
    urlpatterns.append(
        re_path(
            r"^extension-data/(?P<path>.*)",
            lambda *a, **kw: HttpResponse(),
            name="extension-data",
        )
    )
