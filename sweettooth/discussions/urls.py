
from django.conf.urls.defaults import patterns, include, url
from discussions import views

urlpatterns = patterns('',
    url(r'^posted/$', views.comment_done, name='comments-comment-done'),
)
