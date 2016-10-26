
import os.path

from django.conf.urls import patterns, include, url, handler404, handler500
from django.conf import settings
from django.http import HttpResponse

from django.contrib import admin
from django.views import static
from django.contrib.staticfiles import urls as static_urls
admin.autodiscover()

urlpatterns = patterns('',
    # 'login' and 'register'
    url(r'^accounts/', include('sweettooth.auth.urls')),
    url(r'^', include('sweettooth.extensions.urls'), name='index'),

    url(r'^review/', include('sweettooth.review.urls')),
    url(r'^errors/', include('sweettooth.errorreports.urls')),

    url(r'^admin/', include(admin.site.urls)),
    url(r'^comments/', include('sweettooth.ratings.urls')),
    url(r'^comments/', include('django_comments.urls')),

)

if settings.DEBUG:
    # Use static.serve for development...
    urlpatterns.append(url(r'^extension-data/(?P<path>.*)', static.serve,
                           dict(document_root=settings.MEDIA_ROOT), name='extension-data'))
else:
    # and a dummy to reverse on for production.
    urlpatterns.append(url(r'^extension-data/(?P<path>.*)', lambda *a, **kw: HttpResponse(),
                           name='extension-data'))
