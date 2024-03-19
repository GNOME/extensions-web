import django_comments as comments
from django.contrib.messages import info
from django.http import HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import redirect
from django.template.defaultfilters import linebreaks
from django.urls import reverse
from django.utils.dateformat import format as format_date

from sweettooth.decorators import ajax_view
from sweettooth.extensions import models
from sweettooth.utils import gravatar_url


def comment_done(request):
    pk = request.GET["c"]
    comment = comments.get_model().objects.get(pk=pk)
    info(request, "Thank you for your comment")
    return redirect(comment.get_content_object_url())


def comment_details(request, comment):
    extension = comment.content_object
    gravatar = gravatar_url(request, comment.email)
    is_extension_creator = comment.user == extension.creator
    display_name = comment.user.get_full_name() if comment.user else "nobody"

    details = dict(
        gravatar=gravatar,
        is_extension_creator=is_extension_creator,
        comment=linebreaks(comment.comment, autoescape=True),
        author=dict(
            username=display_name,
            url=(
                reverse("auth-profile", kwargs=dict(user=comment.user.username))
                if comment.user
                else None
            ),
        ),
        date=dict(
            timestamp=comment.submit_date.isoformat(),
            standard=format_date(comment.submit_date, "F j, Y"),
        ),
    )

    if comment.rating > -1:
        details["rating"] = comment.rating

    return details


@ajax_view
def get_comments(request):
    try:
        extension = models.Extension.objects.get(pk=request.GET.get("pk"))
    except (models.Extension.DoesNotExist, ValueError):
        return HttpResponseNotFound()

    if not extension.allow_comments:
        return HttpResponseForbidden()

    show_all = request.GET.get("all") == "true"

    comment_list = comments.get_model().objects.for_model(extension)
    comment_list = comment_list.order_by("-submit_date")

    if not show_all:
        comment_list = comment_list[:5]

    return [comment_details(request, comment) for comment in comment_list]
