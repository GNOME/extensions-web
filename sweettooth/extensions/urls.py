
from django.conf.urls.defaults import patterns, include, url
from django.views.generic.simple import direct_to_template

from extensions import views, models, feeds

upload_patterns = patterns('',
    url(r'^$', views.upload_file, dict(pk=None), name='extensions-upload-file'),
    url(r'^new-version/(?P<pk>\d+)/$', views.upload_file, name='extensions-upload-file'),
)

ajax_patterns = patterns('',
    url(r'^edit/(?P<pk>\d+)', views.ajax_inline_edit_view, name='extensions-ajax-inline'),
    url(r'^submit/(?P<pk>\d+)', views.ajax_submit_and_lock_view, name='extensions-ajax-submit'),
    url(r'^upload/screenshot/(?P<pk>\d+)', views.ajax_upload_screenshot_view, name='extensions-ajax-screenshot'),
    url(r'^upload/icon/(?P<pk>\d+)', views.ajax_upload_icon_view, name='extensions-ajax-icon'),
    url(r'^detail/', views.ajax_details_view, name='extensions-ajax-details'),

    url(r'^set-status/active/', views.ajax_set_status_view,
        dict(newstatus=models.STATUS_ACTIVE), name='extensions-ajax-set-status-active'),
    url(r'^set-status/inactive/', views.ajax_set_status_view,
        dict(newstatus=models.STATUS_INACTIVE), name='extensions-ajax-set-status-inactive'),
    url(r'^extensions-list/', views.ajax_extensions_list),
    url(r'^adjust-popularity/', views.ajax_adjust_popularity_view),
    url(r'^adjust-rating/', views.ajax_adjust_rating_view),
)

shell_patterns = patterns('',
    url(r'^extension-query/', views.ajax_query_view),

    url(r'^extension-info/', views.ajax_details_view),

    url(r'^download-extension/(?P<uuid>.+)\.shell-extension\.zip$',
        views.shell_download),

    url(r'^update-info/', views.shell_update, name='extensions-shell-update'),
)

urlpatterns = patterns('',
    url(r'^$', direct_to_template, dict(template='extensions/list.html'), name='extensions-index'),

    url(r'^about/$', direct_to_template, dict(template='extensions/about.html'), name='extensions-about'),

    # we ignore PK of extension, and get extension from version PK
    url(r'^extension/(?P<ext_pk>\d+)/(?P<slug>.+)/version/(?P<pk>.*)/$',
        views.extension_version_view, name='extensions-version-detail'),

    url(r'^extension/(?P<pk>\d+)/(?P<slug>.+)/$',
        views.extension_view, name='extensions-detail'),
    url(r'^extension/(?P<pk>\d+)/$',
        views.extension_view, dict(slug=None), name='extensions-detail'),

    url(r'^local/', direct_to_template, dict(template='extensions/local.html'), name='extensions-local'),

    url(r'^rss/', feeds.LatestExtensionsFeed(), name='extensions-rss-feed'),

    url(r'^upload/', include(upload_patterns)),
    url(r'^ajax/', include(ajax_patterns)),
    url(r'', include(shell_patterns)),
)
