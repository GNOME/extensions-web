
from django.conf.urls import include, url
from sweettooth.ratings import views

urlpatterns = [
    url(r'^posted/$', views.comment_done, name='comments-comment-done'),
    url(r'^all/$', views.get_comments),
]
