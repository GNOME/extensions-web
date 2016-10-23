
import os.path

from django.conf.urls import patterns, include, url, handler404, handler500
from django.conf import settings
from django.http import HttpResponse

from django.contrib import admin
from django.views import static
admin.autodiscover()

urlpatterns = patterns('',
    # 'login' and 'register'
    url(r'^accounts/', include('auth.urls')),
    url(r'^', include('extensions.urls'), name='index'),

    url(r'^review/', include('review.urls')),
    url(r'^errors/', include('errorreports.urls')),

    url(r'^admin/', include(admin.site.urls)),
    url(r'^comments/', include('ratings.urls')),
    url(r'^comments/', include('django.contrib.comments.urls')),

)

if settings.DEBUG:
    # Use static.serve for development...
    urlpatterns.append(url(r'^static/extension-data/(?P<path>.*)', static.serve,
                           dict(document_root=settings.MEDIA_ROOT), name='extension-data'))
else:
    # and a dummy to reverse on for production.
    urlpatterns.append(url(r'^static/extension-data/(?P<path>.*)', lambda *a, **kw: HttpResponse(),
                           name='extension-data'))
