
import base64
from collections import Counter
import itertools
import os.path
from urllib.parse import urljoin

import pygments
import pygments.util
import pygments.lexers
import pygments.formatters

from django.conf import settings
from django.core.mail import EmailMessage
from django.http import HttpResponseForbidden, Http404
from django.shortcuts import redirect, get_object_or_404, render
from django.template import Context
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST

from sweettooth.review.diffutils import get_chunks
from sweettooth.review.models import CodeReview, get_all_reviewers
from sweettooth.extensions import models

from sweettooth.decorators import ajax_view, model_view

IMAGE_TYPES = {
    '.png':  'image/png',
    '.jpg':  'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif':  'image/gif',
    '.bmp':  'image/bmp',
    '.svg':  'image/svg+xml',
}

# Keep this in sync with the BINARY_TYPES list at the top of review.js
BINARY_TYPES = set(['.mo', '.compiled'])

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

def highlight_file(filename, raw, formatter):
    try:
        lexer = pygments.lexers.guess_lexer_for_filename(filename, raw,
                                                         encoding='chardet')
    except pygments.util.ClassNotFound:
        # released pygments doesn't yet have .json
        # so hack around it here.
        if filename.endswith('.json'):
            lexer = pygments.lexers.get_lexer_by_name('js')
        else:
            lexer = pygments.lexers.get_lexer_by_name('text')

    try:
        return pygments.highlight(raw, lexer, formatter)
    except TypeError:
        # Fallback to UTF-8 for old broken pygments version
        lexer.encoding = "utf-8"
        return pygments.highlight(raw, lexer, formatter)

def html_for_file(filename, raw):
    base, extension = os.path.splitext(filename)

    if extension in BINARY_TYPES:
        return None
    elif extension in IMAGE_TYPES:
        mime = IMAGE_TYPES[extension]
        raw_base64 = base64.standard_b64encode(raw)
        return dict(raw=True, html='<img src="data:%s;base64,%s">' % (mime, raw_base64,))
    else:
        return dict(raw=False, lines=highlight_file(filename, raw, code_formatter).splitlines())

def get_old_version(version):
    extension = version.extension

    # Try to get the latest version that's less than the current version
    # that actually has a source field. Sometimes the upload validation
    # fails, so work around it here.
    try:
        old_version = extension.versions.filter(version__lt=version.version).exclude(source="").latest()
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
            yield version.get_zipfile('r')

def grab_lines(zipfile, filename):
    try:
        f = zipfile.open(filename, 'r')
    except KeyError:
        return None
    else:
        content = f.read().decode('utf-8')
        f.close()
        return content.splitlines()

def get_file_list(zipfile):
    return set(n for n in zipfile.namelist() if not n.endswith('/'))

def get_file_changeset(old_zipfile, new_zipfile):
    new_filelist = get_file_list(new_zipfile)

    if old_zipfile is None:
        return dict(unchanged=[],
                    changed=[],
                    added=sorted(new_filelist),
                    deleted=[])

    old_filelist = get_file_list(old_zipfile)

    both    = new_filelist & old_filelist
    added   = new_filelist - old_filelist
    deleted = old_filelist - new_filelist

    unchanged, changed = set([]), set([])

    for filename in both:
        old, new = old_zipfile.open(filename, 'r'), new_zipfile.open(filename, 'r')
        oldcontent, newcontent = old.read(), new.read()

        # Unchanged, remove
        if oldcontent == newcontent:
            unchanged.add(filename)
        else:
            changed.add(filename)

    return dict(unchanged=sorted(unchanged),
                changed=sorted(changed),
                added=sorted(added),
                deleted=sorted(deleted))

@ajax_view
@model_view(models.ExtensionVersion)
def ajax_get_file_list_view(request, version):
    old_zipfile, new_zipfile = get_zipfiles(get_old_version(version), version)
    return get_file_changeset(old_zipfile, new_zipfile)

@ajax_view
@model_view(models.ExtensionVersion)
def ajax_get_file_diff_view(request, version):
    filename = request.GET['filename']

    file_base, file_extension = os.path.splitext(filename)
    if file_extension in IMAGE_TYPES:
        return None

    if file_extension in BINARY_TYPES:
        return None

    old_zipfile, new_zipfile = get_zipfiles(get_old_version(version), version)
    oldlines, newlines = grab_lines(old_zipfile, filename), grab_lines(new_zipfile, filename)

    chunks = list(get_chunks(oldlines, newlines))
    return dict(chunks=chunks,
                oldlines=oldlines,
                newlines=newlines)

def get_changelog(old_version, new_version, filename='CHANGELOG'):
    old_zipfile, new_zipfile = get_zipfiles(old_version, new_version)
    oldlines, newlines = grab_lines(old_zipfile, filename), grab_lines(new_zipfile, filename)
    chunks = get_chunks(oldlines, newlines)

    contents = []
    for chunk in chunks:
        if chunk['operation'] != 'insert':
            continue

        content = '\n'.join(newlines[line['newindex']] for line in chunk['lines'])
        contents.append(content)

    return '\n\n'.join(contents)


@ajax_view
@model_view(models.ExtensionVersion)
def ajax_get_file_view(request, obj):
    zipfile = obj.get_zipfile('r')
    filename = request.GET['filename']

    try:
        f = zipfile.open(filename, 'r')
    except KeyError:
        raise Http404()

    raw = f.read()
    if request.GET.get('raw', False):
        return raw
    else:
        return html_for_file(filename, raw)

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

    status_string = request.POST.get('status')
    newstatus = dict(approve=models.STATUS_ACTIVE,
                     wait=models.STATUS_WAITING,
                     reject=models.STATUS_REJECTED).get(status_string, None)

    # If a normal user didn't change the status and it was in WAITING,
    # change it back to UNREVIEWED
    if not can_approve and version.status == models.STATUS_WAITING:
        newstatus = models.STATUS_UNREVIEWED

    review = CodeReview(version=version,
                        reviewer=request.user,
                        comments=request.POST.get('comments'))

    if newstatus is not None:
        if newstatus == models.STATUS_ACTIVE and not can_approve:
            return HttpResponseForbidden()
        elif newstatus == models.STATUS_REJECTED and not can_approve:
            return HttpResponseForbidden()

        review.new_status = newstatus
        version.status = newstatus
        version.save()

    review.save()

    models.reviewed.send(sender=request, request=request,
                         version=version, review=review)

    return redirect('review-list')

@model_view(models.ExtensionVersion)
def review_version_view(request, obj):
    extension, version = obj.extension, obj

    # Reviews on all versions of the same extension.
    all_versions = extension.versions.order_by('-version')

    # Other reviews on the same version.
    previous_reviews = version.reviews.all()

    has_old_version = get_old_version(version) is not None
    can_approve = can_approve_extension(request.user, extension)
    can_review = can_review_extension(request.user, extension)

    context = dict(extension=extension,
                   version=version,
                   all_versions=all_versions,
                   previous_reviews=previous_reviews,
                   has_old_version=has_old_version,
                   can_approve=can_approve,
                   can_review=can_review)

    return render(request, 'review/review.html', context)

def render_mail(version, template, data):
    extension = version.extension

    data.update(version=version, extension=extension)

    subject_template = 'review/%s_mail_subject.txt' % (template,)
    body_template = 'review/%s_mail.txt' % (template,)

    # TODO: review autoescape
    subject = render_to_string(subject_template, data)
    body = render_to_string(body_template, data)

    references = "<%s-review-v%d@extensions.gnome.org>" % (extension.uuid, version.version)
    headers = {'In-Reply-To': references,
               'References': references}

    return EmailMessage(subject=subject.strip(), body=body.strip(), headers=headers)

def send_email_submitted(version):
    extension = version.extension

    recipient_list = list(get_all_reviewers().values_list('email', flat=True))

    message = render_mail(version, 'submitted', {
        'url': urljoin(
            settings.BASE_URL,
            reverse('review-version', kwargs=dict(pk=version.pk))
        ),
    })
    message.to = recipient_list
    message.extra_headers.update({'X-SweetTooth-Purpose': 'NewExtension',
                                  'X-SweetTooth-ExtensionCreator': extension.creator.username})

    message.send()

def send_email_auto_approved(version):
    extension = version.extension

    review_url = urljoin(settings.BASE_URL, f'/review/{version.pk}')
    version_url = urljoin(settings.BASE_URL, version.get_absolute_url())

    recipient_list = list(get_all_reviewers().values_list('email', flat=True))
    recipient_list.append(extension.creator.email)

    data = dict(version_url=version_url,
                review_url=review_url)

    message = render_mail(version, 'auto_approved', data)
    message.to = recipient_list
    message.extra_headers.update({'X-SweetTooth-Purpose': 'AutoApproved',
                                  'X-SweetTooth-ExtensionCreator': extension.creator.username})
    message.send()

def should_auto_approve_changeset(changes):
    for filename in itertools.chain(changes['changed'], changes['added']):
        # metadata.json updates are safe.
        if filename == 'metadata.json':
            continue

        name, ext = os.path.splitext(os.path.basename(filename))

        # Harmless common metadata files.
        if name in ['README', 'CHANGELOG', 'COPYING', 'LICENSE']:
            continue

        # Translations and stylesheet updates are safe.
        if ext in ['.mo', '.po', '.css']:
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

    if can_review or trusted:
        return True 

    old_version = version.extension.latest_version
    if old_version is None:
        return False

    old_session_modes = set(
        x.mode
        for x in old_version.session_modes.all()
    )
    session_modes = [x.mode for x in version.session_modes.all()]

    if Counter(old_session_modes) != Counter(session_modes):
        return False

    old_zipfile, new_zipfile = get_zipfiles(old_version, version)
    changeset = get_file_changeset(old_zipfile, new_zipfile)
    return should_auto_approve_changeset(changeset)

def extension_submitted(sender, version, **kwargs):
    if should_auto_approve(version):
        CodeReview.objects.create(version=version,
                                  reviewer=sender,
                                  comments="",
                                  new_status=models.STATUS_ACTIVE,
                                  auto=True)
        version.status = models.STATUS_ACTIVE
        version.save()
        send_email_auto_approved(version)
    else:
        send_email_submitted(version)

models.submitted_for_review.connect(extension_submitted)

def send_email_on_reviewed(sender, request, version, review, **kwargs):
    extension = version.extension

    url = request.build_absolute_uri(reverse('review-version',
                                             kwargs=dict(pk=version.pk)))

    data = dict(review=review,
                url=url)

    recipient_list = list(version.reviews.values_list('reviewer__email', flat=True).distinct())
    recipient_list.append(extension.creator.email)

    if review.reviewer.email in recipient_list:
        # Don't spam the reviewer with his own review.
        recipient_list.remove(review.reviewer.email)

    message = render_mail(version, 'reviewed', data)
    message.to = recipient_list
    message.extra_headers.update({'X-SweetTooth-Purpose': 'NewReview',
                                  'X-SweetTooth-Reviewer': review.reviewer.username})
    message.send()

models.reviewed.connect(send_email_on_reviewed)
