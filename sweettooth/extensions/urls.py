from django.conf.urls import include
from django.urls import path, re_path
from django.views.generic.base import TemplateView

from sweettooth.extensions import feeds, models, views

ajax_patterns = [
    re_path(
        r"^edit/(?P<pk>\d+)", views.ajax_inline_edit_view, name="extensions-ajax-inline"
    ),
    re_path(
        r"^upload/screenshot/(?P<pk>\d+)",
        views.ajax_upload_screenshot_view,
        name="extensions-ajax-screenshot",
    ),
    re_path(
        r"^upload/icon/(?P<pk>\d+)",
        views.ajax_upload_icon_view,
        name="extensions-ajax-icon",
    ),
    re_path(r"^detail/", views.ajax_details_view, name="extensions-ajax-details"),
    re_path(
        r"^set-status/active/",
        views.ajax_set_status_view,
        dict(newstatus=models.STATUS_ACTIVE),
        name="extensions-ajax-set-status-active",
    ),
    re_path(
        r"^set-status/inactive/",
        views.ajax_set_status_view,
        dict(newstatus=models.STATUS_INACTIVE),
        name="extensions-ajax-set-status-inactive",
    ),
    re_path(r"^adjust-popularity/", views.ajax_adjust_popularity_view),
]

shell_patterns = [
    re_path(r"^extension-query/", views.ajax_query_view, name="extensions-query"),
    re_path(r"^extension-info/", views.ajax_details_view),
    re_path(
        r"^download-extension/(?P<uuid>.+)\.shell-extension\.zip$",
        views.shell_download,
        name="extensions-shell-download",
    ),
    re_path(r"^update-info/", views.shell_update, name="extensions-shell-update"),
]

urlpatterns = [
    re_path(
        r"^$",
        TemplateView.as_view(template_name="extensions/list.html"),
        name="extensions-index",
    ),
    re_path(
        r"^about/$",
        TemplateView.as_view(template_name="extensions/about.html"),
        name="extensions-about",
    ),
    path("away/<str:target_url>", views.AwayView.as_view(), name="away"),
    re_path(
        r"^extension/(?P<pk>\d+)/(?P<slug>.+)/$",
        views.extension_view,
        name="extensions-detail",
    ),
    re_path(
        r"^extension/(?P<pk>\d+)/$",
        views.extension_view,
        dict(slug=None),
        name="extensions-detail",
    ),
    re_path(
        r"^local/",
        TemplateView.as_view(template_name="extensions/local.html"),
        name="extensions-local",
    ),
    re_path(r"^rss/", feeds.LatestExtensionsFeed(), name="extensions-rss-feed"),
    re_path(r"^upload/", views.upload_file, name="extensions-upload-file"),
    re_path(r"^ajax/", include(ajax_patterns)),
    re_path(r"", include(shell_patterns)),
]
