
import os.path

from django.conf.urls import include, url, handler404, handler500
from django.conf import settings
from django.http import HttpResponse

from django.contrib import admin
from django.views import static
from django.views.generic.base import TemplateView
from django.views.i18n import JavaScriptCatalog

admin.autodiscover()

urlpatterns = [
    # 'login' and 'register'
    url(r'^accounts/', include('sweettooth.auth.urls')),
    url(r'^', include('sweettooth.extensions.urls'), name='index'),

    url(r'^review/', include('sweettooth.review.urls')),
    url(r'^errors/', include('sweettooth.errorreports.urls')),

    url(r'^jsi18n/$', JavaScriptCatalog.as_view(), name='javascript-catalog'),
    url(r'^admin/', admin.site.urls),
    url(r'^comments/', include('sweettooth.ratings.urls')),
    url(r'^comments/', include('django_comments.urls')),
    url(r'^robots\.txt$', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
]

if settings.DEBUG:
    # Use static.serve for development...
    urlpatterns.append(url(r'^extension-data/(?P<path>.*)', static.serve,
                           dict(document_root=settings.MEDIA_ROOT), name='extension-data'))
else:
    # and a dummy to reverse on for production.
    urlpatterns.append(url(r'^extension-data/(?P<path>.*)', lambda *a, **kw: HttpResponse(),
                           name='extension-data'))
