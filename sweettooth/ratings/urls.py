from django.urls import re_path

from sweettooth.ratings import views

urlpatterns = [
    re_path(r"^posted/$", views.comment_done, name="comments-comment-done"),
    re_path(r"^all/$", views.get_comments),
]
