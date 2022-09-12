from django.urls import re_path

from sweettooth.extensions import views, feeds

urlpatterns = [
    re_path(r'^rss/', feeds.LatestExtensionsFeed(), name='extensions-rss-feed'),
    re_path(r'^download-extension/(?P<uuid>.+)\.shell-extension\.zip$',
        views.shell_download, name='extensions-shell-download'),
    re_path(r'^update-info/', views.shell_update, name='extensions-shell-update'),
]
