from django.urls import path, re_path
from django.views.generic.list import ListView

from sweettooth.extensions.models import ExtensionVersion
from sweettooth.review import views

urlpatterns = [
    re_path(
        r"^$",
        ListView.as_view(
            template_name="review/list.html",
            queryset=ExtensionVersion.objects.unreviewed().order_by("pk"),
            context_object_name="version_list",
        ),
        name="review-list",
    ),
    re_path(
        r"^ajax/get-file/(?P<pk>\d+)",
        views.ajax_get_file_view,
        name="review-ajax-files",
    ),
    path(
        "ajax/get-file-list/<int:pk>",
        views.ajax_get_file_list_view,
        name="review-ajax-file-list",
    ),
    path(
        "ajax/get-file-list/<int:pk>/<int:old_version_pk>",
        views.ajax_get_file_list_view,
    ),
    path(
        r"ajax/get-file-diff/<int:pk>",
        views.ajax_get_file_diff_view,
        name="review-ajax-file-diff",
    ),
    path(
        "ajax/get-file-diff/<int:pk>/<int:old_version_pk>",
        views.ajax_get_file_diff_view,
        name="review-ajax-file-diff-against",
    ),
    re_path(r"^submit/(?P<pk>\d+)", views.submit_review_view, name="review-submit"),
    re_path(
        r"^download/(?P<pk>\d+)\.shell-extension.zip$",
        views.download_zipfile,
        name="review-download",
    ),
    re_path(r"^(?P<pk>\d+)", views.review_version_view, name="review-version"),
]
