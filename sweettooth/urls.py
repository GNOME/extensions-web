
import os.path

from django.conf.urls.defaults import patterns, include, url, handler404, handler500
from django.conf import settings

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
    url(r'^comments/', include('discussions.urls')),
    url(r'^comments/', include('django.contrib.comments.urls')),

)

if settings.DEBUG:
    # Use static.serve for development...
    urlpatterns.append(url(r'^static/extension-data/(?P<path>.*)', static.serve,
                           dict(document_root=settings.MEDIA_ROOT), name='extension-data'))
else:
    # and a dummy to reverse on for production.
    urlpatterns.append(url(r'^static/extension-data/(?P<path>.*)', lambda n: None,
                           name='extension-data'))

if settings.DEBUG:
    # XXX - I need to be shot for this
    # Because we need HTTPS + Apache to test, in debug use
    # static.serve to serve admin media
    admin_media_dir = os.path.join(os.path.dirname(admin.__file__), 'media')
    admin_media_prefix = settings.ADMIN_MEDIA_PREFIX.strip('/')

    urlpatterns.append(url(r'^%s(?P<path>.*)' % (admin_media_prefix,),
                           static.serve, dict(document_root=admin_media_dir)))
