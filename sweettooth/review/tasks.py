from collections.abc import Sequence

from celery import shared_task
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.mail import EmailMessage, get_connection
from django.db.models import Q
from django.template.loader import render_to_string

from sweettooth.extensions import models
from sweettooth.review.models import CodeReview


def get_all_reviewers():
    perm = Permission.objects.get(
        codename="can-review-extensions", content_type__app_label="review"
    )

    # Dark magic to get all the users with a specific permission
    # Thanks to <schinckel> in #django
    groups = Group.objects.filter(permissions=perm)
    return (
        get_user_model()
        .objects.filter(
            Q(is_superuser=True) | Q(user_permissions=perm) | Q(groups__in=groups)
        )
        .distinct()
    )


def render_mail(version, template, data) -> EmailMessage:
    extension = version.extension

    data.update(version=version, extension=extension)

    subject_template = "review/%s_mail_subject.txt" % (template,)
    body_template = "review/%s_mail.txt" % (template,)

    subject = render_to_string(subject_template, data)
    body = render_to_string(body_template, data)

    references = "<%s-review-v%d@extensions.gnome.org>" % (
        extension.uuid,
        version.version,
    )
    headers = {"In-Reply-To": references, "References": references}

    return EmailMessage(subject=subject.strip(), body=body.strip(), headers=headers)


def send_mass_mail(
    subject: str, message: str, recipients: Sequence[str], headers: dict[str, str]
):
    connection = get_connection()
    messages = [
        EmailMessage(
            subject, message, None, [recipient], connection=connection, headers=headers
        )
        for recipient in recipients
    ]

    return connection.send_messages(messages)


@shared_task
def send_review_submitted_email(version_id: int, review_url: str):
    version = models.ExtensionVersion.objects.select_related("extension").get(
        pk=version_id
    )
    extension = version.extension

    data = {"url": review_url}
    recipient_list = list(get_all_reviewers().values_list("email", flat=True))
    message = render_mail(version, "submitted", data)
    message.extra_headers.update(
        {
            "X-SweetTooth-Purpose": "NewExtension",
            "X-SweetTooth-ExtensionCreator": extension.creator.username,
        }
    )
    send_mass_mail(message.subject, message.body, recipient_list, message.extra_headers)


@shared_task
def send_auto_approved_email(version_id: int, review_url: str, version_url: str):
    version = models.ExtensionVersion.objects.select_related("extension").get(
        pk=version_id
    )
    extension = version.extension

    data = {"review_url": review_url, "version_url": version_url}
    recipient_list = list(get_all_reviewers().values_list("email", flat=True))
    recipient_list.append(extension.creator.email)
    message = render_mail(version, "auto_approved", data)
    message.extra_headers.update(
        {
            "X-SweetTooth-Purpose": "AutoApproved",
            "X-SweetTooth-ExtensionCreator": extension.creator.username,
        }
    )
    send_mass_mail(message.subject, message.body, recipient_list, message.extra_headers)


@shared_task
def send_reviewed_email(version_id: int, review_id: int, review_url: str):
    version = models.ExtensionVersion.objects.select_related("extension").get(
        pk=version_id
    )
    extension = version.extension
    review = CodeReview.objects.select_related("reviewer").get(pk=review_id)

    data = {"review": review, "url": review_url}
    recipient_list = list(
        version.reviews.values_list("reviewer__email", flat=True).distinct()
    )
    recipient_list.append(extension.creator.email)

    if review.reviewer and review.reviewer.email in recipient_list:
        recipient_list.remove(review.reviewer.email)

    message = render_mail(version, "reviewed", data)
    message.extra_headers.update(
        {
            "X-SweetTooth-Purpose": "NewReview",
            "X-SweetTooth-Reviewer": review.reviewer.username
            if review.reviewer
            else "",
        }
    )
    send_mass_mail(message.subject, message.body, recipient_list, message.extra_headers)
