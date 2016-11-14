
import json
from math import ceil

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator, InvalidPage
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseForbidden, HttpResponseServerError, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from extensions import models, search
from extensions.forms import UploadForm

from decorators import ajax_view, model_view

def get_versions_for_version_strings(version_strings):
    def get_version(major, minor, point):
        try:
            return models.ShellVersion.objects.get(major=major, minor=minor, point=point)
        except models.ShellVersion.DoesNotExist:
            return None

    for version_string in version_strings:
        try:
            major, minor, point = models.parse_version_string(version_string)
        except models.InvalidShellVersion:
            continue

        version = get_version(major, minor, point)
        if version:
            yield version

        # If we already have a base version, don't bother querying it again...
        if point == -1:
            continue

        base_version = get_version(major, minor, -1)
        if base_version:
            yield base_version

def grab_proper_extension_version(extension, shell_version):
    shell_versions = set(get_versions_for_version_strings([shell_version]))
    if not shell_versions:
        return None

    versions = extension.visible_versions.filter(shell_versions__in=shell_versions)
    if versions.count() < 1:
        return None
    else:
        return versions.order_by('-version')[0]

def find_extension_version_from_params(extension, params):
    vpk = params.get('version_tag', '')
    shell_version = params.get('shell_version', '')

    if shell_version:
        return grab_proper_extension_version(extension, shell_version)
    elif vpk:
        try:
            return extension.visible_versions.get(pk=int(vpk))
        except models.ExtensionVersion.DoesNotExist:
            return None
    else:
        return None

def shell_download(request, uuid):
    extension = get_object_or_404(models.Extension.objects.visible(), uuid=uuid)
    version = find_extension_version_from_params(extension, request.GET)

    if version is None:
        raise Http404()

    extension.downloads += 1
    extension.save(replace_metadata_json=False)

    return redirect(version.source.url)

@ajax_view
def shell_update(request):
    installed = json.loads(request.GET['installed'])
    shell_version = request.GET['shell_version']
    operations = {}

    for uuid, meta in installed.iteritems():
        try:
            version = meta['version']
        except (KeyError, TypeError):
            # XXX - if the user has a locally installed version of
            # an extension on SweetTooth, what should we do?
            continue

        try:
            extension = models.Extension.objects.get(uuid=uuid)
        except models.Extension.DoesNotExist:
            continue

        try:
            version_obj = extension.versions.get(version=version)
        except models.ExtensionVersion.DoesNotExist:
            # The user may have a newer version than what's on the site.
            continue

        proper_version = grab_proper_extension_version(extension, shell_version)

        if proper_version is not None:
            if version < proper_version.version:
                operations[uuid] = "upgrade"
            elif version_obj.status == models.STATUS_REJECTED:
                operations[uuid] = "downgrade"
        else:
            operations[uuid] = "blacklist"

    return operations

def ajax_query_params_query(request, versions, n_per_page):
    version_qs = models.ExtensionVersion.objects.visible()

    if versions is not None:
        version_qs = version_qs.filter(shell_versions__in=versions)

    queryset = models.Extension.objects.distinct().filter(versions__in=version_qs)

    uuids = request.GET.getlist('uuid')
    if uuids:
        queryset = queryset.filter(uuid__in=uuids)

    sort = request.GET.get('sort', 'popularity')
    sort = dict(recent='created').get(sort, sort)
    if sort not in ('created', 'downloads', 'popularity', 'name'):
        raise Http404()

    queryset = queryset.order_by(sort)

    # Sort by ASC for name, DESC for everything else.
    if sort == 'name':
        default_order = 'asc'
    else:
        default_order = 'desc'

    order = request.GET.get('order', default_order)
    queryset.query.standard_ordering = (order == 'asc')

    if n_per_page == -1:
        return queryset, 1

    # Paginate the query
    paginator = Paginator(queryset, n_per_page)
    page = request.GET.get('page', 1)
    try:
        page_number = int(page)
    except ValueError:
        raise Http404()

    try:
        page_obj = paginator.page(page_number)
    except InvalidPage:
        raise Http404()

    return page_obj.object_list, paginator.num_pages

def ajax_query_search_query(request, versions, n_per_page):
    querystring = request.GET.get('search', '')

    database, enquire = search.enquire(querystring, versions)

    page = request.GET.get('page', 1)
    try:
        offset = (int(page) - 1) * n_per_page
    except ValueError:
        raise Http404()

    if n_per_page == -1:
        mset = enquire.get_mset(offset, database.get_doccount())
        num_pages = 1
    else:
        mset = enquire.get_mset(offset, n_per_page)
        num_pages = int(ceil(float(mset.get_matches_estimated()) / n_per_page))

    pks = [match.document.get_data() for match in mset]

    # filter doesn't guarantee an order, so we need to get all the
    # possible models then look them up to get the ordering
    # returned by xapian. This hits the database all at once, rather
    # than pagesize times.
    extension_lookup = {}
    for extension in models.Extension.objects.filter(pk__in=pks):
        extension_lookup[str(extension.pk)] = extension

    extensions = [extension_lookup[pk] for pk in pks]

    return extensions, num_pages

@ajax_view
def ajax_query_view(request):
    try:
        n_per_page = int(request.GET['n_per_page'])
    except (KeyError, ValueError), e:
        n_per_page = 10

    version_strings = request.GET.getlist('shell_version')
    if version_strings and version_strings not in (['all'], ['-1']):
        versions = set(get_versions_for_version_strings(version_strings))
    else:
        versions = None

    if request.GET.get('search',  ''):
        func = ajax_query_search_query
    else:
        func = ajax_query_params_query

    object_list, num_pages = func(request, versions, n_per_page)

    return dict(extensions=[ajax_details(e) for e in object_list],
                total=len(object_list),
                numpages=num_pages)

@model_view(models.Extension)
def extension_view(request, obj, **kwargs):
    extension, versions = obj, obj.visible_versions

    if versions.count() == 0 and not extension.user_can_edit(request.user):
        raise Http404()

    # Redirect if we don't match the slug.
    slug = kwargs.get('slug')

    if slug != extension.slug:
        kwargs.update(dict(slug=extension.slug,
                           pk=extension.pk))
        return redirect(extension)

    # If the user can edit the model, let him do so.
    if extension.user_can_edit(request.user):
        template_name = "extensions/detail_edit.html"
    else:
        template_name = "extensions/detail.html"

    context = dict(shell_version_map = json.dumps(extension.visible_shell_version_map),
                   extension = extension,
                   all_versions = extension.versions.order_by('-version'),
                   is_visible = extension.latest_version is not None)
    return render(request, template_name, context)

@require_POST
@ajax_view
def ajax_adjust_popularity_view(request):
    uuid = request.POST['uuid']
    action = request.POST['action']

    try:
        extension = models.Extension.objects.get(uuid=uuid)
    except models.Extension.DoesNotExist:
        raise Http404()

    pop = models.ExtensionPopularityItem(extension=extension)

    if action == 'enable':
        pop.offset = +1
    elif action == 'disable':
        pop.offset = -1
    else:
        return HttpResponseServerError()

    pop.save()

@ajax_view
@require_POST
@model_view(models.Extension)
def ajax_inline_edit_view(request, extension):
    if not extension.user_can_edit(request.user):
        return HttpResponseForbidden()

    key = request.POST['id']
    value = request.POST['value']
    if key.startswith('extension_'):
        key = key[len('extension_'):]

    if key == 'name':
        extension.name = value
    elif key == 'description':
        extension.description = value
    elif key == 'url':
        extension.url = value
    else:
        return HttpResponseForbidden()

    models.extension_updated.send(sender=extension, extension=extension)

    extension.save()

    return value

@ajax_view
@require_POST
@model_view(models.Extension)
def ajax_upload_screenshot_view(request, extension):
    extension.screenshot = request.FILES['file']
    extension.save(replace_metadata_json=False)
    return extension.screenshot.url

@ajax_view
@require_POST
@model_view(models.Extension)
def ajax_upload_icon_view(request, extension):
    extension.icon = request.FILES['file']
    extension.save(replace_metadata_json=False)
    return extension.icon.url

def ajax_details(extension, version=None):
    details = dict(uuid = extension.uuid,
                   name = extension.name,
                   creator = extension.creator.username,
                   creator_url = reverse('auth-profile', kwargs=dict(user=extension.creator.username)),
                   pk = extension.pk,
                   description = extension.description,
                   link = extension.get_absolute_url(),
                   icon = extension.icon.url,
                   screenshot = extension.screenshot.url if extension.screenshot else None,
                   shell_version_map = extension.visible_shell_version_map)

    if version is not None:
        download_url = reverse('extensions-shell-download', kwargs=dict(uuid=extension.uuid))
        details['version'] = version.version
        details['version_tag'] = version.pk
        details['download_url'] = "%s?version_tag=%d" % (download_url, version.pk)
    return details

@ajax_view
def ajax_details_view(request):
    uuid = request.GET.get('uuid', None)
    pk = request.GET.get('pk', None)

    if uuid is not None:
        extension = get_object_or_404(models.Extension.objects.visible(), uuid=uuid)
    elif pk is not None:
        extension = get_object_or_404(models.Extension.objects.visible(), pk=pk)
    else:
        raise Http404()

    version = find_extension_version_from_params(extension, request.GET)
    return ajax_details(extension, version)

@ajax_view
def ajax_set_status_view(request, newstatus):
    pk = request.GET['pk']

    version = get_object_or_404(models.ExtensionVersion, pk=pk)
    extension = version.extension

    if not extension.user_can_edit(request.user):
        return HttpResponseForbidden()

    if version.status not in (models.STATUS_ACTIVE, models.STATUS_INACTIVE):
        return HttpResponseForbidden()

    version.status = newstatus
    version.save()

    context = dict(version=version,
                   extension=extension)

    return dict(svm=json.dumps(extension.visible_shell_version_map),
                mvs=render_to_string('extensions/multiversion_status.html', context))

@transaction.commit_manually
def create_version(request, file_source):
    try:
        metadata = models.parse_zipfile_metadata(file_source)
        uuid = metadata['uuid']
    except (models.InvalidExtensionData, KeyError), e:
        messages.error(request, "Invalid extension data: %s" % (e.message,))
        transaction.rollback()
        return None, []

    try:
        extension = models.Extension.objects.get(uuid=uuid)
    except models.Extension.DoesNotExist:
        extension = models.Extension(creator=request.user)
    else:
        if request.user != extension.creator and not request.user.is_superuser:
            messages.error(request, "An extension with that UUID has already been added.")
            transaction.rollback()
            return None, []

    extension.parse_metadata_json(metadata)
    extension.save()

    try:
        extension.full_clean()
    except ValidationError, e:
        transaction.rollback()
        return None, e.messages

    version = models.ExtensionVersion.objects.create(extension=extension,
                                                     source=file_source,
                                                     status=models.STATUS_UNREVIEWED)
    version.parse_metadata_json(metadata)
    version.replace_metadata_json()
    version.save()

    transaction.commit()
    return version, []

@login_required
def upload_file(request):
    errors = []
    if request.method == 'POST':
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            file_source = form.cleaned_data['source']
            version, errors = create_version(request, file_source)
            if version is not None:
                models.submitted_for_review.send(sender=request, request=request, version=version)
                return redirect(version.extension)
    else:
        form = UploadForm()

    return render(request, 'extensions/upload.html', dict(form=form,
                                                          errors=errors))
