
from django.conf.urls import patterns, url
from django.views.generic.list import ListView

from sweettooth.extensions.models import ExtensionVersion
from sweettooth.review import views

urlpatterns = patterns('',
    url(r'^$', ListView.as_view(template_name='review/list.html',
                                queryset=ExtensionVersion.objects.unreviewed(),
                                context_object_name='version_list'),
        name='review-list'),
    url(r'^ajax/get-file/(?P<pk>\d+)', views.ajax_get_file_view, name='review-ajax-files'),
    url(r'^ajax/get-file-list/(?P<pk>\d+)', views.ajax_get_file_list_view, name='review-ajax-file-list'),
    url(r'^ajax/get-file-diff/(?P<pk>\d+)', views.ajax_get_file_diff_view, name='review-ajax-file-diff'),
    url(r'^submit/(?P<pk>\d+)', views.submit_review_view, name='review-submit'),

    url(r'^download/(?P<pk>\d+)\.shell-extension.zip$',
        views.download_zipfile, name='review-download'),

    url(r'^(?P<pk>\d+)', views.review_version_view, name='review-version'),

)
