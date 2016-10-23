
from django.conf.urls import patterns, include, url
from django.views.generic.base import TemplateView

from extensions import views, models, feeds

ajax_patterns = patterns('',
    url(r'^edit/(?P<pk>\d+)', views.ajax_inline_edit_view, name='extensions-ajax-inline'),
    url(r'^upload/screenshot/(?P<pk>\d+)', views.ajax_upload_screenshot_view, name='extensions-ajax-screenshot'),
    url(r'^upload/icon/(?P<pk>\d+)', views.ajax_upload_icon_view, name='extensions-ajax-icon'),
    url(r'^detail/', views.ajax_details_view, name='extensions-ajax-details'),

    url(r'^set-status/active/', views.ajax_set_status_view,
        dict(newstatus=models.STATUS_ACTIVE), name='extensions-ajax-set-status-active'),
    url(r'^set-status/inactive/', views.ajax_set_status_view,
        dict(newstatus=models.STATUS_INACTIVE), name='extensions-ajax-set-status-inactive'),
    url(r'^adjust-popularity/', views.ajax_adjust_popularity_view),
)

shell_patterns = patterns('',
    url(r'^extension-query/', views.ajax_query_view, name='extensions-query'),

    url(r'^extension-info/', views.ajax_details_view),

    url(r'^download-extension/(?P<uuid>.+)\.shell-extension\.zip$',
        views.shell_download, name='extensions-shell-download'),

    url(r'^update-info/', views.shell_update, name='extensions-shell-update'),
)

urlpatterns = patterns('',
    url(r'^$', TemplateView.as_view(template_name='extensions/list.html'), name='extensions-index'),

    url(r'^about/$', TemplateView.as_view(template_name='extensions/about.html'), name='extensions-about'),

    url(r'^extension/(?P<pk>\d+)/(?P<slug>.+)/$',
        views.extension_view, name='extensions-detail'),
    url(r'^extension/(?P<pk>\d+)/$',
        views.extension_view, dict(slug=None), name='extensions-detail'),

    url(r'^local/', TemplateView.as_view(template_name='extensions/local.html'), name='extensions-local'),

    url(r'^rss/', feeds.LatestExtensionsFeed(), name='extensions-rss-feed'),

    url(r'^upload/', views.upload_file, name='extensions-upload-file'),
    url(r'^ajax/', include(ajax_patterns)),
    url(r'', include(shell_patterns)),
)
