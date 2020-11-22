"""
    GNOME Shell Extensions Repository
    Copyright (C) 2011-2016 Jasper St. Pierre <jstpierre@mecheye.net>
    Copyright (C) 2016-2020 Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""

import json
from functools import reduce
from typing import Any
from urllib.parse import unquote

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import BadRequest
from django.core.paginator import InvalidPage, Paginator
from django.core.validators import URLValidator
from django.db import transaction
from django.forms import ValidationError
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseServerError,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic.base import TemplateView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from sweettooth.decorators import ajax_view, model_view
from sweettooth.exceptions import DatabaseErrorWithMessages
from sweettooth.extensions import models, serializers
from sweettooth.extensions.documents import ExtensionDocument
from sweettooth.extensions.forms import ImageUploadForm, UploadForm
from sweettooth.extensions.templatetags.extension_icon import extension_icon


class ExtensionsPagination(PageNumberPagination):
    page_size = settings.REST_FRAMEWORK["PAGE_SIZE"]
    page_size_query_param = "page_size"
    max_page_size = 100


class ExtensionsViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    lookup_field = "uuid"
    lookup_value_regex = "[-a-zA-Z0-9@._]+"
    serializer_class = serializers.ExtensionSerializer
    pagination_class = ExtensionsPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ["created", "downloads", "popularity", "?"]
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_queryset(self):
        uuids = self.request.query_params.getlist("uuid[]")
        status = self.request.query_params.get("status")
        queryset = models.Extension.objects.all()

        if uuids:
            queryset = queryset.filter(uuid__in=uuids)

        if status is not None and status.isnumeric():
            status = int(status)

        if status in models.STATUSES:
            queryset = queryset.filter(versions__status=status).distinct()

        return queryset

    @action(methods=["post"], detail=False, parser_classes=[JSONParser])
    def updates(self, request):
        installed = self.request.data.get("installed")
        shell_version = self.request.data.get("shell_version")
        version_validation_disabled = self.request.data.get(
            "version_validation_disabled", False
        )

        if not installed:
            return Response()

        extensions = models.Extension.objects.filter(uuid__in=installed.keys())

        result = {}
        for uuid, version in installed.items():
            try:
                version = int(version)
            except (KeyError, TypeError):
                continue
            except ValueError:
                version = 1

            extension = reduce(
                lambda x, y, uuid=uuid: (
                    x if x and x.uuid == uuid else y if y and y.uuid == uuid else None
                ),
                list(extensions),
            )

            if not extension:
                continue

            try:
                version = extension.versions.get(version=version)
            except models.ExtensionVersion.DoesNotExist:
                # Skip unknown versions
                continue

            proper_version = grab_proper_extension_version(
                extension, shell_version, version_validation_disabled
            )

            if proper_version is not None and proper_version.version != version.version:
                result[uuid] = {
                    "action": "change",
                    "version": proper_version.version,
                }

        return Response(result)

    @action(methods=["get"], detail=False, url_path="search/(?P<query>[^/.]+)")
    def search(self, request, query=None):
        try:
            page = int(
                self.request.query_params.get(self.pagination_class.page_query_param, 1)
            )
            page_size = max(
                1,
                min(
                    self.max_page_size,
                    int(
                        self.request.query_params.get(
                            self.page_size_query_param, self.page_size
                        )
                    ),
                ),
            )
        except Exception as ex:
            print(ex)
            return Response(status=status.HTTP_400_BAD_REQUEST)

        if not query:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        queryset = ExtensionDocument.search().query(
            "multi_match", query=query, fields=ExtensionDocument.document_fields()
        )

        ordering = self.request.query_params.get("ordering")
        ordering_field = (
            ordering if not ordering or ordering[0] != "-" else ordering[1:]
        )
        if ordering and ordering_field in self.ordering_fields:
            queryset = queryset.sort(ordering)

        paginator = Paginator(queryset.to_queryset(), page_size)

        return Response(
            {
                "count": paginator.count,
                "results": self.serializer_class(
                    [sr for sr in paginator.page(page).object_list],
                    many=True,
                    context={"request": request},
                ).data,
            }
        )


def get_versions_for_version_strings(version_strings):
    def get_version(major, minor, point):
        try:
            return models.ShellVersion.objects.get(
                major=major, minor=minor, point=point
            )
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
        if (major < 40 and point == -1) or minor == -1:
            continue

        base_version = get_version(major, minor, -1)
        if base_version:
            yield base_version

        if major >= 40:
            base_version = get_version(major, -1, -1)
            if base_version:
                yield base_version


def grab_proper_extension_version(
    extension, shell_version, disable_version_validation: bool = False
) -> models.ExtensionVersion | None:
    def get_best_shell_version():
        visible_versions = extension.visible_versions

        supported_shell_versions = set(
            shell_version
            for version in visible_versions
            for shell_version in version.shell_versions.all()
        )

        if not supported_shell_versions:
            return None

        supported_shell_versions = sorted(
            supported_shell_versions, key=lambda x: (x.major, x.minor, x.point)
        )
        requested_shell_version = models.parse_version_string(shell_version)

        if (
            supported_shell_versions[0].major,
            supported_shell_versions[0].minor,
            supported_shell_versions[0].point,
        ) > requested_shell_version:
            versions = visible_versions.filter(
                shell_versions=supported_shell_versions[0]
            )
        else:
            supported_shell_versions = list(
                shell_version
                for shell_version in supported_shell_versions
                if (shell_version.major, shell_version.minor, shell_version.point)
                <= requested_shell_version
            )
            versions = visible_versions.filter(
                shell_versions=supported_shell_versions[-1]
            )

        return versions.order_by("-version")[0]

    shell_versions = set(get_versions_for_version_strings([shell_version]))
    if not shell_versions:
        return get_best_shell_version() if disable_version_validation else None

    versions = extension.visible_versions.filter(shell_versions__in=shell_versions)
    if versions.count() < 1:
        return get_best_shell_version() if disable_version_validation else None
    else:
        return versions.order_by("-version")[0]


def find_extension_version_from_params(extension, params):
    vpk = params.get("version_tag")
    shell_version = params.get("shell_version", "")
    disable_version_validation = (
        False
        if params.get("disable_version_validation", "1").lower() in ["0", "false"]
        else True
    )

    if shell_version:
        return grab_proper_extension_version(
            extension, shell_version, disable_version_validation
        )
    elif vpk:
        try:
            return extension.visible_versions.get(pk=int(vpk))
        except (models.ExtensionVersion.DoesNotExist, ValueError):
            return None
    else:
        return None


def shell_download(request, uuid):
    extension = get_object_or_404(models.Extension.objects.visible(), uuid=uuid)
    try:
        version = find_extension_version_from_params(extension, request.GET)
    except models.InvalidShellVersion:
        return HttpResponseBadRequest()

    if version is None:
        raise Http404()

    extension.downloads += 1
    extension.save()

    return redirect(version.source.url)


@ajax_view
@csrf_exempt
def shell_update(request):
    try:
        if request.method == "POST":
            installed = json.load(request)
        # TODO: drop GET request support at year after chrome-gnome-shell 11 release
        else:
            installed = json.loads(request.GET["installed"])
        shell_version = request.GET["shell_version"]
        disable_version_validation = request.GET.get(
            "disable_version_validation", False
        )
    except (KeyError, ValueError):
        return HttpResponseBadRequest()

    operations = {}

    for uuid, meta in installed.items():
        try:
            version = int(meta["version"])
        except (KeyError, TypeError):
            # XXX - if the user has a locally installed version of
            # an extension on SweetTooth, what should we do?
            continue
        except ValueError:
            version = 1

        try:
            extension = models.Extension.objects.get(uuid=uuid)
        except models.Extension.DoesNotExist:
            continue

        try:
            version_obj = extension.versions.get(version=version)
        except models.ExtensionVersion.DoesNotExist:
            # The user may have a newer version than what's on the site.
            continue

        try:
            proper_version = grab_proper_extension_version(
                extension, shell_version, disable_version_validation
            )
        except models.InvalidShellVersion:
            return HttpResponseBadRequest()

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

    """  # noqa: E501
    TODO: this is produces temporary table.
    SELECT DISTINCT
       `extensions_extension`.`id`, `extensions_extension`.`name`, `extensions_extension`.`uuid`, `extensions_extension`.`slug`,
       `extensions_extension`.`creator_id`, `extensions_extension`.`description`, `extensions_extension`.`url`,
       `extensions_extension`.`created`, `extensions_extension`.`downloads`, `extensions_extension`.`popularity`,
       `extensions_extension`.`allow_comments`, `extensions_extension`.`screenshot`, `extensions_extension`.`icon`
    FROM `extensions_extension`
    INNER JOIN `extensions_extensionversion` ON (`extensions_extension`.`id` = `extensions_extensionversion`.`extension_id`)
    WHERE `extensions_extensionversion`.`id` IN (SELECT U0.`id` FROM `extensions_extensionversion` U0 WHERE U0.`status` = 3)
    ORDER BY `extensions_extension`.`popularity` DESC

    We must cache "active" ExtensionVersion state in Extension model and use it in filter
    """
    queryset = models.Extension.objects.distinct().filter(versions__in=version_qs)

    uuids = request.GET.getlist("uuid")
    if uuids:
        queryset = queryset.filter(uuid__in=uuids)

    sort = request.GET.get("sort", "popularity")
    if sort == "relevance":
        sort = "popularity"

    if sort not in ("created", "downloads", "popularity", "name"):
        raise Http404()

    queryset = queryset.order_by(sort, "uuid")

    # Sort by ASC for name, DESC for everything else.
    if sort == "name":
        default_order = "asc"
    else:
        default_order = "desc"

    order = request.GET.get("order", default_order)
    queryset.query.standard_ordering = order == "asc"

    if n_per_page == -1:
        return queryset, 1

    # Paginate the query
    paginator = Paginator(queryset, n_per_page)
    page = request.GET.get("page", 1)
    try:
        page_number = int(page)
    except ValueError:
        raise Http404()

    try:
        page_obj = paginator.page(page_number)
    except InvalidPage:
        raise Http404()

    return page_obj.object_list, paginator.num_pages


def ajax_query_search_query(
    request, versions: set[models.ShellVersion], n_per_page: int
):
    max_page_size = 100
    ordering_fields = ["name", "created", "downloads", "popularity"]
    try:
        page = int(request.GET.get("page", 1))
        page_size = max(1, min(max_page_size, int(n_per_page)))
    except Exception:
        raise BadRequest()

    query = request.GET.get("search", "")
    if not query:
        raise BadRequest()

    queryset = (
        ExtensionDocument.search()
        .extra(size=5000)
        .query(
            "multi_match",
            query=query,
            type="best_fields",
            fields=[
                "uuid",
                "name^3",
                "description",
                "creator^2",
            ],
        )
    )

    if versions:
        queryset = queryset.filter(
            "terms", shell_versions=[str(version) for version in versions]
        )

    order_by = request.GET.get("sort", "relevance")

    if order_by in ordering_fields:
        if order_by in ("name",):
            order_by = f"{order_by}.raw"
        else:
            order_by = f"-{order_by}"

        queryset = queryset.sort(order_by)

    paginator = Paginator(queryset.to_queryset(keep_order=True), page_size)

    try:
        return ([sr for sr in paginator.page(page).object_list], paginator.num_pages)
    except InvalidPage:
        return ([], 0)


@ajax_view
def ajax_query_view(request):
    try:
        n_per_page = int(request.GET["n_per_page"])
        if n_per_page == 1000:
            from django.conf import settings

            # This is GNOME Software request. Let's redirect it to static file
            return redirect((settings.STATIC_URL + "extensions.json"), permanent=True)

        n_per_page = min(n_per_page, 25)
    except (KeyError, ValueError):
        n_per_page = 10

    version_strings = request.GET.getlist("shell_version")
    if version_strings and version_strings not in (["all"], ["-1"]):
        versions = set(get_versions_for_version_strings(version_strings))
    else:
        versions = None

    if request.GET.get("search", ""):
        func = ajax_query_search_query
    else:
        func = ajax_query_params_query

    object_list, num_pages = func(request, versions, n_per_page)

    return dict(
        extensions=[ajax_details(e) for e in object_list],
        total=len(object_list),
        numpages=num_pages,
    )


@model_view(models.Extension)
def extension_view(request, obj, **kwargs):
    extension, versions = obj, obj.visible_versions
    can_edit = extension.user_can_edit(request.user)

    if versions.count() == 0 and not can_edit:
        raise Http404()

    # Redirect if we don't match the slug.
    slug = kwargs.get("slug")

    if slug != extension.slug:
        kwargs.update(dict(slug=extension.slug, pk=extension.pk))
        return redirect(extension)

    # If the user can edit the model, let him do so.
    if can_edit:
        template_name = "extensions/detail_edit.html"
    else:
        template_name = "extensions/detail.html"

    donation_urls = extension.donation_urls.all().order_by("url_type")

    context = dict(
        shell_version_map=json.dumps(extension.visible_shell_version_map),
        extension=extension,
        extension_uses_unlock_dialog=extension.uses_session_mode("unlock-dialog"),
        all_versions=extension.versions.order_by("-version"),
        visible_versions=json.dumps(extension.visible_shell_version_array),
        is_visible=extension.latest_version is not None,
        next=extension.get_absolute_url(),
        donation_urls=donation_urls,
        can_edit=can_edit,
        show_versions=can_edit or request.user.has_perm("review.can-review-extensions"),
    )
    return render(request, template_name, context)


@require_POST
@ajax_view
def ajax_adjust_popularity_view(request):
    uuid = request.POST["uuid"]
    action = request.POST["action"]

    try:
        extension = models.Extension.objects.get(uuid=uuid)
    except models.Extension.DoesNotExist:
        raise Http404()

    pop = models.ExtensionPopularityItem(extension=extension)

    if action == "enable":
        pop.offset = +1
    elif action == "disable":
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

    key = request.POST["id"]
    value = request.POST["value"]
    if key.startswith("extension_"):
        key = key[len("extension_") :]

    if key == "name":
        extension.name = value
    elif key == "description":
        extension.description = value
    elif key == "url":
        extension.url = value
    else:
        return HttpResponseForbidden()

    extension.full_clean()
    extension.save()

    return value


def validate_uploaded_image(request, extension):
    if not extension.user_can_edit(request.user):
        return HttpResponseForbidden()

    form = ImageUploadForm(request.POST, request.FILES)

    if not form.is_valid():
        return JsonResponse(form.errors.get_json_data(), status=403)

    if form.cleaned_data["file"].size > 2 * 1024 * 1024:
        return HttpResponseForbidden(content="Too big image")

    return form.cleaned_data["file"]


@ajax_view
@require_POST
@model_view(models.Extension)
def ajax_upload_screenshot_view(request, extension):
    data = validate_uploaded_image(request, extension)
    if isinstance(data, HttpResponse):
        return data

    extension.screenshot = data
    extension.full_clean()
    extension.save()
    return extension.screenshot.url


@ajax_view
@require_POST
@model_view(models.Extension)
def ajax_upload_icon_view(request, extension):
    data = validate_uploaded_image(request, extension)
    if isinstance(data, HttpResponse):
        return data

    extension.icon = data
    extension.full_clean()
    extension.save()
    return extension.icon.url


def ajax_details(extension, version=None):
    details = dict(
        uuid=extension.uuid,
        name=extension.name,
        creator=extension.creator.get_full_name(),
        creator_url=reverse(
            "auth-profile", kwargs=dict(user=extension.creator.username)
        ),
        pk=extension.pk,
        description=extension.description,
        link=extension.get_absolute_url(),
        icon=extension_icon(extension.icon),
        screenshot=extension.screenshot.url if extension.screenshot else None,
        shell_version_map=extension.visible_shell_version_map,
        downloads=extension.downloads,
        url=extension.url,
        donation_urls=[
            d.full_url for d in extension.donation_urls.all().order_by("url_type")
        ],
    )

    if version is not None:
        download_url = reverse(
            "extensions-shell-download", kwargs=dict(uuid=extension.uuid)
        )
        details["version"] = version.version
        details["version_tag"] = version.pk
        details["download_url"] = "%s?version_tag=%d" % (download_url, version.pk)
    return details


@ajax_view
def ajax_details_view(request):
    uuid = request.GET.get("uuid", "")
    pk = request.GET.get("pk", None)

    if len(uuid) > 2 and len(uuid) <= models.Extension.uuid.field.max_length:
        extension = get_object_or_404(models.Extension.objects.visible(), uuid=uuid)
    elif pk:
        try:
            extension = get_object_or_404(models.Extension.objects.visible(), pk=pk)
        except (TypeError, ValueError):
            raise Http404()
    else:
        return HttpResponseBadRequest()

    try:
        version = find_extension_version_from_params(extension, request.GET)
    except models.InvalidShellVersion:
        return HttpResponseBadRequest()

    return ajax_details(extension, version)


@ajax_view
def ajax_set_status_view(request, newstatus):
    pk = request.GET["pk"]

    version = get_object_or_404(models.ExtensionVersion, pk=pk)
    extension = version.extension

    if not extension.user_can_edit(request.user):
        return HttpResponseForbidden()

    if version.status not in (models.STATUS_ACTIVE, models.STATUS_INACTIVE):
        return HttpResponseForbidden()

    version.status = newstatus
    version.save()

    context = dict(version=version, extension=extension)

    return dict(
        svm=json.dumps(extension.visible_shell_version_map),
        mvs=render_to_string("extensions/multiversion_status.html", context),
    )


def create_version(request, file_source):
    try:
        with transaction.atomic():
            try:
                metadata = models.parse_zipfile_metadata(file_source)
                uuid = metadata["uuid"]
            except (models.InvalidExtensionData, KeyError) as e:
                messages.error(request, "Invalid extension data: %s" % (e.message,))
                raise DatabaseErrorWithMessages

            try:
                extension = models.Extension.objects.get(uuid=uuid)
                extension.update_from_metadata(metadata)
            except models.Extension.DoesNotExist:
                extension = models.Extension(creator=request.user, metadata=metadata)
            else:
                if request.user != extension.creator and not request.user.is_superuser:
                    messages.error(
                        request, "An extension with that UUID has already been added."
                    )
                    raise DatabaseErrorWithMessages

            extension.full_clean()
            extension.save()

            if "version-name" in metadata:
                version_name = metadata.pop("version-name").strip()
            else:
                version_name = None

            version = models.ExtensionVersion(
                extension=extension,
                metadata=metadata,
                source=file_source,
                status=models.STATUS_UNREVIEWED,
                version_name=version_name,
            )

            version.full_clean()
            version.save()

            return version, []
    except (DatabaseErrorWithMessages, ValidationError) as e:
        return None, e.messages


@login_required
def upload_file(request):
    errors = []
    if request.method == "POST":
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            file_source = form.cleaned_data["source"]
            version, errors = create_version(request, file_source)
            if version is not None:
                models.submitted_for_review.send(
                    sender=request, request=request, version=version
                )
                return redirect(version.extension)
    else:
        form = UploadForm()

    return render(request, "extensions/upload.html", dict(form=form, errors=errors))


class AwayView(TemplateView):
    template_name = "extensions/away.html"
    _validator = URLValidator(schemes=("http", "https"))

    def setup(self, request, *args: Any, **kwargs: Any) -> None:
        super().setup(request, *args, **kwargs)
        self.target_url = unquote(kwargs["target_url"])

    def get(self, request, *args, **kwargs):
        try:
            self._validator(self.target_url)
            kwargs["target_url"] = self.target_url
        except ValidationError:
            return redirect("/")

        return super().get(request, *args, **kwargs)
