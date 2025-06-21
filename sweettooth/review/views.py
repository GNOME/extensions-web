import base64
import itertools
import os.path
import stat
from collections import Counter
from collections.abc import Iterable, Sequence
from contextlib import ExitStack
from typing import IO
from zipfile import ZipFile, ZipInfo

import chardet
import pygments
import pygments.formatters
import pygments.lexers
import pygments.util
from django.core.mail import EmailMessage, get_connection
from django.http import Http404, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST

from sweettooth.decorators import ajax_view, model_view
from sweettooth.extensions import models
from sweettooth.review.diffutils import get_chunks
from sweettooth.review.models import CodeReview, get_all_reviewers

IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
}

# Keep this in sync with the BINARY_TYPES list at the top of review.js
BINARY_TYPES = set([".mo", ".compiled"])


# Stolen from ReviewBoard
# See the top of diffutils.py for details
class NoWrapperHtmlFormatter(pygments.formatters.HtmlFormatter):
    """An HTML Formatter for Pygments that don't wrap items in a div."""

    def _wrap_div(self, inner):
        # Method called by the formatter to wrap the contents of inner.
        # Inner is a list of tuples containing formatted code. If the first item
        # in the tuple is zero, then it's a wrapper, so we should ignore it.
        for tup in inner:
            if tup[0]:
                yield tup


code_formatter = NoWrapperHtmlFormatter(style="borland", cssclass="code")


def can_review_extension(user, extension):
    if user == extension.creator:
        return True

    if user.has_perm("review.can-review-extensions"):
        return True

    return False


def can_approve_extension(user, extension):
    return user.has_perm("review.can-review-extensions")


# The `detect_encoding` function code is mostly from Pygments which is
# licensed under BSD 2-clause license.
# Copyright (c) 2006-2022 by the respective authors (see AUTHORS file).
# All rights reserved.
# https://github.com/pygments/pygments/blob/2.19.1/LICENSE
# https://github.com/pygments/pygments/blob/2.19.1/pygments/lexer.py#L212
def detect_encoding(text: bytes):
    _encoding_map = [
        (b"\xef\xbb\xbf", "utf-8"),
        (b"\xff\xfe\0\0", "utf-32"),
        (b"\0\0\xfe\xff", "utf-32be"),
        (b"\xff\xfe", "utf-16"),
        (b"\xfe\xff", "utf-16be"),
    ]

    # check for BOM first
    decoded = None
    for bom, encoding in _encoding_map:
        if text.startswith(bom):
            return encoding

    # no BOM found, so use chardet
    if decoded is None:
        enc = chardet.detect(text[:1024])  # Guess using first 1KB
        encoding = enc.get("encoding") or "utf-8"

        # Probably wrong detection due to
        # https://github.com/chardet/chardet/issues/292
        # The Windows-1254 encoding looks uncommon for GNOME extensions
        if isinstance(encoding, str) and encoding.lower() == "windows-1254":
            return "utf-8"

        return encoding


def highlight_file(filename, raw: bytes, formatter):
    try:
        lexer = pygments.lexers.guess_lexer_for_filename(
            filename, raw, encoding=detect_encoding(raw)
        )
    except pygments.util.ClassNotFound:
        # released pygments doesn't yet have .json
        # so hack around it here.
        if filename.endswith(".json"):
            lexer = pygments.lexers.get_lexer_by_name("js")
        else:
            lexer = pygments.lexers.get_lexer_by_name("text")

    try:
        return pygments.highlight(raw, lexer, formatter)
    except (TypeError, UnicodeDecodeError):
        # Fallback to UTF-8 for old broken pygments version
        lexer.encoding = "utf-8"
        return pygments.highlight(raw, lexer, formatter)


def html_for_file(filename: str, file: IO[bytes], is_symlink: bool):
    _, extension = os.path.splitext(filename)

    if not is_symlink:
        if extension in BINARY_TYPES:
            return None
        elif extension in IMAGE_TYPES:
            mime = IMAGE_TYPES[extension]
            return dict(
                raw=True,
                html='<img src="data:%s;base64,%s">'
                % (
                    mime,
                    base64.standard_b64encode(file.read()).decode("ascii"),
                ),
            )

    return dict(
        raw=False,
        lines=highlight_file(filename, file.read(), code_formatter).splitlines(),
    )


def get_old_version(version):
    extension = version.extension

    # Try to get the latest version that's less than the current version
    # that actually has a source field. Sometimes the upload validation
    # fails, so work around it here.
    try:
        old_version = (
            extension.versions.filter(
                version__lt=version.version,
                status__in=(models.STATUS_ACTIVE, models.STATUS_INACTIVE),
            )
            .exclude(source="")
            .latest()
        )
    except models.ExtensionVersion.DoesNotExist:
        try:
            old_version = (
                extension.versions.filter(version__lt=version.version)
                .exclude(source="")
                .earliest()
            )
        except models.ExtensionVersion.DoesNotExist:
            # There's nothing before us that has a source, or this is the
            # first version.
            return None

    return old_version


def get_zipfiles(*args: tuple[models.ExtensionVersion]):
    for version in args:
        if version is None:
            yield None
        else:
            yield version.get_zipfile("r")


def grab_lines(zipfile: ZipFile, filename: str):
    try:
        with zipfile.open(filename, "r") as f:
            return f.read().decode("utf-8").splitlines()
    except (KeyError, UnicodeDecodeError):
        return None


def get_file_info(zipfile) -> set[ZipInfo]:
    return set(n for n in zipfile.infolist() if not n.filename.endswith("/"))


def get_file_list(fileinfo: Iterable[ZipInfo]) -> set[str]:
    return {i.filename for i in fileinfo}


def is_symlink(external_attr: int):
    return stat.S_ISLNK((external_attr >> 16) & 0xFFFF)


def get_symlinks(fileinfo: Iterable[ZipInfo]) -> set[str]:
    return {i.filename for i in fileinfo if is_symlink(i.external_attr)}


def get_file_changeset(old_zipfile: ZipFile | None, new_zipfile: ZipFile):
    with new_zipfile:
        new_fileinfo = get_file_info(new_zipfile)
        new_filelist = get_file_list(new_fileinfo)
        new_symlinks = get_symlinks(new_fileinfo)

        if old_zipfile is None:
            return dict(
                unchanged=[],
                changed=[],
                added=sorted(new_filelist),
                deleted=[],
                symlinks=list(new_symlinks),
            )

        with old_zipfile:
            old_fileinfo = get_file_info(old_zipfile)
            old_filelist = get_file_list(old_fileinfo)

            both = new_filelist & old_filelist
            added = new_filelist - old_filelist
            deleted = old_filelist - new_filelist

            unchanged, changed = set(), set()

            for filename in both:
                with (
                    old_zipfile.open(filename, "r") as old,
                    new_zipfile.open(filename, "r") as new,
                ):
                    while True:
                        oldcontent, newcontent = old.read(1024), new.read(1024)
                        if not oldcontent or not newcontent:
                            if oldcontent or newcontent:
                                changed.add(filename)
                            else:
                                unchanged.add(filename)

                            break

                        if oldcontent != newcontent:
                            changed.add(filename)
                            break

            return dict(
                unchanged=sorted(unchanged),
                changed=sorted(changed),
                added=sorted(added),
                deleted=sorted(deleted),
                symlinks=list(new_symlinks),
            )


@ajax_view
@model_view(models.ExtensionVersion)
def ajax_get_file_list_view(request, version, old_version_pk: int | None = None):
    if old_version_pk:
        old_version = get_object_or_404(models.ExtensionVersion, pk=old_version_pk)
        if old_version.extension != version.extension:
            return HttpResponseBadRequest()
    else:
        old_version = get_old_version(version)

    return get_file_changeset(*get_zipfiles(old_version, version))


@ajax_view
@model_view(models.ExtensionVersion)
def ajax_get_file_diff_view(
    request, version: models.ExtensionVersion, old_version_pk: int | None = None
):
    filename = request.GET["filename"]

    _, file_extension = os.path.splitext(filename)
    if file_extension in IMAGE_TYPES:
        return None

    if file_extension in BINARY_TYPES:
        return None

    if old_version_pk:
        old_version = get_object_or_404(models.ExtensionVersion, pk=old_version_pk)
        if old_version.extension != version.extension:
            return None
    else:
        old_version = get_old_version(version)

    old_zipfile, new_zipfile = get_zipfiles(old_version, version)
    oldlines, newlines = (
        grab_lines(old_zipfile, filename),
        grab_lines(new_zipfile, filename),
    )

    chunks = list(get_chunks(oldlines, newlines))
    return dict(chunks=chunks, oldlines=oldlines, newlines=newlines)


def get_changelog(old_version, new_version, filename="CHANGELOG"):
    old_zipfile, new_zipfile = get_zipfiles(old_version, new_version)
    oldlines, newlines = (
        grab_lines(old_zipfile, filename),
        grab_lines(new_zipfile, filename),
    )
    chunks = get_chunks(oldlines, newlines)

    contents = []
    for chunk in chunks:
        if chunk["operation"] != "insert":
            continue

        content = "\n".join(newlines[line["newindex"]] for line in chunk["lines"])
        contents.append(content)

    return "\n\n".join(contents)


@ajax_view
@model_view(models.ExtensionVersion)
def ajax_get_file_view(request, obj: models.ExtensionVersion):
    filename = request.GET["filename"]

    with obj.get_zipfile("r") as zipfile:
        try:
            with zipfile.open(filename, "r") as f:
                return html_for_file(
                    filename, f, is_symlink(zipfile.getinfo(filename).external_attr)
                )
        except KeyError:
            raise Http404()


def download_zipfile(request, pk):
    version = get_object_or_404(models.ExtensionVersion, pk=pk)
    return redirect(version.source.url)


@require_POST
@model_view(models.ExtensionVersion)
def submit_review_view(request, obj):
    extension, version = obj.extension, obj

    can_approve = can_approve_extension(request.user, extension)
    can_review = can_review_extension(request.user, extension)

    if not can_review:
        return HttpResponseForbidden()

    status_string = request.POST.get("status")
    newstatus = dict(
        approve=models.STATUS_ACTIVE,
        wait=models.STATUS_WAITING,
        reject=models.STATUS_REJECTED,
    ).get(status_string, None)

    if newstatus and not can_approve:
        return HttpResponseForbidden()

    # If a normal user didn't change the status and it was in WAITING,
    # change it back to UNREVIEWED
    if not can_approve and version.status == models.STATUS_WAITING:
        newstatus = models.STATUS_UNREVIEWED

    review = CodeReview(
        version=version, reviewer=request.user, comments=request.POST.get("comments")
    )

    if newstatus:
        review.new_status = newstatus
        version.status = newstatus
        version.save()

    review.save()

    models.reviewed.send(
        sender=request, request=request, version=version, review=review
    )

    return redirect("review-list")


@model_view(models.ExtensionVersion)
def review_version_view(request, obj):
    extension, version = obj.extension, obj

    # Reviews on all versions of the same extension.
    all_versions = extension.versions.order_by("-version")

    # Other reviews on the same version.
    previous_reviews = version.reviews.order_by("pk")

    compare_version = get_old_version(version)
    can_approve = can_approve_extension(request.user, extension)
    can_review = can_review_extension(request.user, extension)

    context = dict(
        extension=extension,
        version=version,
        all_versions=all_versions,
        previous_reviews=previous_reviews,
        compare_version=compare_version,
        can_approve=can_approve,
        can_review=can_review,
    )

    return render(request, "review/review.html", context)


def render_mail(version, template, data) -> EmailMessage:
    extension = version.extension

    data.update(version=version, extension=extension)

    subject_template = "review/%s_mail_subject.txt" % (template,)
    body_template = "review/%s_mail.txt" % (template,)

    # TODO: review autoescape
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


def send_email_submitted(request, version):
    extension = version.extension

    url = request.build_absolute_uri(
        reverse("review-version", kwargs=dict(pk=version.pk))
    )

    data = dict(url=url)

    recipient_list = list(get_all_reviewers().values_list("email", flat=True))

    message = render_mail(version, "submitted", data)
    message.extra_headers.update(
        {
            "X-SweetTooth-Purpose": "NewExtension",
            "X-SweetTooth-ExtensionCreator": extension.creator.username,
        }
    )

    send_mass_mail(message.subject, message.body, recipient_list, message.extra_headers)


def send_email_auto_approved(request, version):
    extension = version.extension

    review_url = request.build_absolute_uri(
        reverse("review-version", kwargs=dict(pk=version.pk))
    )
    version_url = request.build_absolute_uri(version.get_absolute_url())

    recipient_list = list(get_all_reviewers().values_list("email", flat=True))
    recipient_list.append(extension.creator.email)

    data = dict(version_url=version_url, review_url=review_url)

    message = render_mail(version, "auto_approved", data)
    message.extra_headers.update(
        {
            "X-SweetTooth-Purpose": "AutoApproved",
            "X-SweetTooth-ExtensionCreator": extension.creator.username,
        }
    )

    send_mass_mail(message.subject, message.body, recipient_list, message.extra_headers)


def should_auto_approve_changeset(changes):
    for filename in itertools.chain(changes["changed"], changes["added"]):
        # metadata.json updates are safe.
        if filename == "metadata.json":
            continue

        name, ext = os.path.splitext(os.path.basename(filename))

        # Harmless common metadata files.
        if name in ["README", "CHANGELOG", "COPYING", "LICENSE"]:
            continue

        # Translations and stylesheet updates are safe.
        if ext in [".mo", ".po", ".css"]:
            continue

        # Image updates are safe.
        if ext in IMAGE_TYPES:
            continue

        return False

    return True


def should_auto_approve(version: models.ExtensionVersion):
    extension = version.extension
    user = extension.creator
    can_review = can_approve_extension(user, extension)
    trusted = user.has_perm("review.trusted")

    if (can_review or trusted) and not user.force_review:
        return True

    old_version: models.ExtensionVersion | None = version.extension.latest_version
    if old_version is None:
        return False

    old_session_modes = set(x.mode for x in old_version.session_modes.all())
    session_modes = [x.mode for x in version.session_modes.all()]

    if Counter(old_session_modes) != Counter(session_modes):
        return False

    old_shell_versions: set[int] = set(
        sv.major for sv in old_version.shell_versions.all()
    )
    new_shell_versions: set[int] = set(sv.major for sv in version.shell_versions.all())

    if any(v >= 45 for v in (new_shell_versions - old_shell_versions)):
        return False

    with ExitStack() as stack:
        old_zipfile, new_zipfile = get_zipfiles(old_version, version)

        stack.enter_context(old_zipfile)
        stack.enter_context(new_zipfile)

        changeset = get_file_changeset(old_zipfile, new_zipfile)
        return should_auto_approve_changeset(changeset)


def extension_submitted(sender, request, version: models.ExtensionVersion, **kwargs):
    if should_auto_approve(version):
        CodeReview.objects.create(
            version=version,
            reviewer=request.user,
            comments="",
            new_status=models.STATUS_ACTIVE,
            auto=True,
        )
        version.status = models.STATUS_ACTIVE
        version.save()
        send_email_auto_approved(request, version)
    else:
        send_email_submitted(request, version)

        unreviewed_versions = version.extension.versions.filter(
            version__lt=version.version,
            status__in=(models.STATUS_UNREVIEWED, models.STATUS_WAITING),
        )

        for _version in unreviewed_versions:
            if set(version.shell_versions.all()) != set(_version.shell_versions.all()):
                continue

            CodeReview.objects.create(
                version=_version,
                reviewer=request.user,
                comments=(
                    "Auto-rejected because of new version"
                    f" {version.display_full_version} was uploaded"
                ),
                new_status=models.STATUS_REJECTED,
                auto=True,
            )
            _version.status = models.STATUS_REJECTED
            _version.save()


models.submitted_for_review.connect(extension_submitted)


def send_email_on_reviewed(sender, request, version, review, **kwargs):
    extension = version.extension

    url = request.build_absolute_uri(
        reverse("review-version", kwargs=dict(pk=version.pk))
    )

    data = dict(review=review, url=url)

    recipient_list = list(
        version.reviews.values_list("reviewer__email", flat=True).distinct()
    )
    recipient_list.append(extension.creator.email)

    if review.reviewer.email in recipient_list:
        # Don't spam the reviewer with his own review.
        recipient_list.remove(review.reviewer.email)

    message = render_mail(version, "reviewed", data)
    message.extra_headers.update(
        {
            "X-SweetTooth-Purpose": "NewReview",
            "X-SweetTooth-Reviewer": review.reviewer.username,
        }
    )

    send_mass_mail(message.subject, message.body, recipient_list, message.extra_headers)


models.reviewed.connect(send_email_on_reviewed)
