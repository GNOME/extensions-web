"""
    GNOME Shell Extensions Repository
    Copyright (C) 2011-2016 Jasper St. Pierre <jstpierre@mecheye.net>
    Copyright (C) 2016-2020 Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""

from functools import reduce
from itertools import product
import json
from urllib.parse import urlencode, urlparse, urlunparse

from django.core.paginator import Paginator
from django.forms import Field
from django.http import (
    HttpResponseBadRequest,
    Http404
)
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse

from django_filters.rest_framework import CharFilter, ChoiceFilter, DjangoFilterBackend, FilterSet, MultipleChoiceFilter

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiParameter

from rest_framework import filters, mixins, parsers, permissions, renderers, viewsets, status
from rest_framework.generics import CreateAPIView
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory

from sweettooth import settings
from sweettooth.api.widgets import QueryArrayWidget
from sweettooth.decorators import ajax_view
from sweettooth.extensions import models, serializers
from sweettooth.extensions.documents import ExtensionDocument

from .renderers import ExtensionVersionZipRenderer


class UUIDFilter(MultipleChoiceFilter, CharFilter):
    field_class = Field


class ExtensionsFilter(FilterSet):
    uuid = UUIDFilter(widget=QueryArrayWidget)
    status = ChoiceFilter(
        field_name='versions__status',
        choices=list(models.STATUSES.items()),
        distinct=True
    )

    class Meta:
        model = models.Extension
        fields = ('uuid', 'status', 'recommended')


class ExtensionsPagination(PageNumberPagination):
    page_size = settings.REST_FRAMEWORK['PAGE_SIZE']
    page_size_query_param = 'page_size'
    max_page_size = 100


class ExtensionsViewSet(mixins.ListModelMixin,
                        mixins.RetrieveModelMixin,
                        viewsets.GenericViewSet):
    queryset = models.Extension.objects.all()
    lookup_field = 'uuid'
    lookup_value_regex = '[-a-zA-Z0-9@._]+'
    serializer_class = serializers.ExtensionSerializer
    pagination_class = ExtensionsPagination
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filterset_class = ExtensionsFilter
    ordering_fields = ['created', 'updated', 'downloads', 'popularity', '?']
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100

    @extend_schema(request=serializers.ExtensionsUpdatesSerializer)
    @action(methods=['post'], detail=False, parser_classes=[JSONParser])
    def updates(self, request):
        updates = serializers.ExtensionsUpdatesSerializer(data=request.data)

        if not updates.is_valid():
            return HttpResponseBadRequest()

        extensions = models.Extension.objects.filter(uuid__in=updates.validated_data['installed'].keys())
        if not extensions.exists():
            return Response({})

        result = {}
        for uuid, update_data in updates.validated_data['installed'].items():
            try:
                version = int(update_data['version'])
            except (KeyError, TypeError):
                continue
            except ValueError:
                version = 1

            extension = reduce(
                lambda x, y, uuid=uuid: (
                    x if x and x.uuid == uuid else
                    y if y and y.uuid == uuid else
                    None
                ),
                list(extensions)
            )

            if not extension:
                continue

            try:
                version = extension.versions.get(version=version)
            except models.ExtensionVersion.DoesNotExist:
                # Skip unknown versions
                continue

            proper_version = grab_proper_extension_version(
                extension,
                updates.validated_data['shell_version'],
                updates.validated_data['version_validation_enabled']
            )

            if proper_version is not None:
                if version.version < proper_version.version:
                    result[uuid] = 'upgrade'
                elif version.status == models.STATUS_REJECTED:
                    result[uuid] = "downgrade"
            else:
                result[uuid] = "blacklist"

        return Response(result)

    @extend_schema(
        parameters=[
            OpenApiParameter(name='recommended', type=OpenApiTypes.BOOL),
            OpenApiParameter(name='ordering', enum=[
                f"{order}{field}"
                for field, order in product(ordering_fields, ('', '-'))
                if field != '?'
            ]),
            OpenApiParameter(name=pagination_class.page_query_param, type=OpenApiTypes.INT),
            OpenApiParameter(name=page_size_query_param, type=OpenApiTypes.INT),
        ]
    )
    @action(methods=['get'], detail=False, url_path='search/(?P<query>[^/.]+)')
    def search(self, request, query=None):
        try:
            page = int(self.request.query_params.get(self.pagination_class.page_query_param, 1))
            page_size = max(
                1,
                min(
                    self.max_page_size,
                    int(self.request.query_params.get(self.page_size_query_param, self.page_size))
                )
            )
        except Exception as ex:
            print(ex)
            return Response(status=status.HTTP_400_BAD_REQUEST)

        if not query or query == '-':
            return Response(status=status.HTTP_400_BAD_REQUEST)

        queryset = ExtensionDocument.search().extra(size=5000).query(
            "multi_match",
            query=query
        )

        if self.request.query_params.get('recommended') in ("true", "1"):
            queryset = queryset.filter("term", recommended=True)

        ordering = self.request.query_params.get('ordering')
        ordering_field = (
            ordering
            if not ordering or ordering[0] != '-'
            else ordering[1:]
        )
        if ordering and ordering_field in self.ordering_fields and ordering_field != '?':
            queryset = queryset.sort(ordering)

        # https://github.com/Codoc-os/django-opensearch-dsl/issues/27
        paginator = Paginator(queryset.to_queryset(keep_order=True), page_size)

        try:
            return Response({
                'count': paginator.count,
                'results': self.serializer_class(
                    [sr for sr in paginator.page(page).object_list],
                    many=True,
                    context={'request': request}
                ).data
            })
        except Exception:
            return Response(status=status.HTTP_400_BAD_REQUEST)


class ExtensionsVersionsViewSet(mixins.ListModelMixin,
                                mixins.RetrieveModelMixin,
                                viewsets.GenericViewSet):
    lookup_field = 'version'
    serializer_class = serializers.ExtensionVersionSerializer
    pagination_class = ExtensionsPagination
    renderer_classes = [
        renderers.JSONRenderer,
        renderers.BrowsableAPIRenderer,
        ExtensionVersionZipRenderer,
    ]
    filter_backends = [DjangoFilterBackend]
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_queryset(self):
        return models.ExtensionVersion.objects.filter(
            extension__uuid=self.kwargs['extension_uuid']
        ).order_by('version')


class ExtensionUploadView(CreateAPIView):
    parser_classes = [parsers.MultiPartParser]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = serializers.ExtensionUploadSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


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
        if (major < 40 and point == -1) or minor == -1:
            continue

        base_version = get_version(major, minor, -1)
        if base_version:
            yield base_version

        if major >= 40:
            base_version = get_version(major, -1, -1)
            if base_version:
                yield base_version


def grab_proper_extension_version(extension, shell_version, version_validation_enabled=False):
    def get_best_shell_version():
        visible_versions = extension.visible_versions

        supported_shell_versions = set(shell_version
                                       for version in visible_versions
                                       for shell_version in version.shell_versions.all())

        if not supported_shell_versions:
            return None

        supported_shell_versions = sorted(supported_shell_versions, key=lambda x: (x.major, x.minor, x.point))
        requested_shell_version = models.parse_version_string(shell_version)

        if (supported_shell_versions[0].major, supported_shell_versions[0].minor,
                supported_shell_versions[0].point) > requested_shell_version:
            versions = visible_versions.filter(shell_versions=supported_shell_versions[0])
        else:
            supported_shell_versions = list(shell_version
                                           for shell_version in supported_shell_versions
                                           if (shell_version.major, shell_version.minor, shell_version.point) <= requested_shell_version)
            versions = visible_versions.filter(shell_versions=supported_shell_versions[-1])

        return versions.order_by('-version')[0]

    shell_versions = set(get_versions_for_version_strings([shell_version]))
    if not shell_versions:
        return get_best_shell_version() if not version_validation_enabled else None

    versions = extension.visible_versions.filter(shell_versions__in=shell_versions)
    if versions.count() < 1:
        return get_best_shell_version() if not version_validation_enabled else None

    return versions.order_by('-version')[0]


def find_extension_version_from_params(extension, params):
    vpk = params.get('version_tag', '')
    shell_version = params.get('shell_version', '')
    disable_version_validation = False if params.get('disable_version_validation', "1").lower() in ["0",
                                                                                                    "false"] else True

    if shell_version:
        return grab_proper_extension_version(extension, shell_version, not disable_version_validation)
    elif vpk:
        try:
            return extension.visible_versions.get(pk=int(vpk))
        except models.ExtensionVersion.DoesNotExist:
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

    url = list(urlparse(reverse(
        'extensions-versions-detail',
        kwargs={
            'extension_uuid': extension.uuid,
            'version': version.version
        }
    )))
    url[4] = urlencode({'format': 'zip'})

    return redirect(urlunparse(url))


@ajax_view
@csrf_exempt
def shell_update(request):
    try:
        if request.method == 'POST':
            installed = json.load(request)
        else:
            return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)
        shell_version = request.GET['shell_version']
        disable_version_validation = request.GET.get('disable_version_validation', False)
    except (KeyError, ValueError):
        return HttpResponseBadRequest()

    mocked_request = APIRequestFactory().post(
        reverse('extension-updates'),
        data={
            'installed': {
                uuid: data | {
                    'uuid': uuid
                }
                for uuid, data in installed.items()
            },
            'shell_version': shell_version,
            'version_validation_enabled': not disable_version_validation,
        }
    )
    return ExtensionsViewSet.as_view({'post': 'updates'})(mocked_request)
