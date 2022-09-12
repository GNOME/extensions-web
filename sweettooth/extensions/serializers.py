"""
    GNOME Shell extensions repository
    Copyright (C) 2020  Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from rest_framework import serializers

from sweettooth.extensions.models import Extension, ExtensionVersion, InvalidExtensionData, ShellVersion
from sweettooth.users.serializers import BaseUserProfileSerializer

from . import models


class ShellVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShellVersion
        fields = [
            'major',
            'minor',
            'point',
        ]


class ExtensionSerializer(serializers.ModelSerializer):
    creator = BaseUserProfileSerializer(many=False, read_only=True)

    class Meta:
        model = Extension
        fields = [
            'id',
            'uuid',
            'name',
            'creator',
            'description',
            'created',
            'updated',
            'downloads',
            'popularity',
            'screenshot',
            'icon',
            'rating',
            'rated',
        ]


class ExtensionVersionSerializer(serializers.ModelSerializer):
    # TODO: change primary key to UUID
    extension = serializers.SlugRelatedField(
        many=False,
        read_only=True,
        slug_field='uuid'
     )
    shell_versions = ShellVersionSerializer(many=True, read_only=True)

    class Meta:
        model = ExtensionVersion
        fields = [
            'extension',
            'version',
            'status',
            'shell_versions',
            'created',
        ]


class InstalledExtensionSerializer(serializers.Serializer):
    version = serializers.CharField(allow_blank=True, default='0')


class ExtensionsUpdatesSerializer(serializers.Serializer):
    installed = serializers.DictField(child=InstalledExtensionSerializer())
    shell_version = serializers.CharField()
    version_validation_enabled = serializers.BooleanField(default=False)


class ExtensionUploadSerializer(serializers.Serializer):
    source = serializers.FileField(required=True)
    shell_license_compliant = serializers.BooleanField(required=True)
    tos_compliant = serializers.BooleanField(required=True)

    def validate_source(self, value):
        try:
            self.metadata = models.parse_zipfile_metadata(value)
            if 'uuid' not in self.metadata:
                raise serializers.ValidationError(_('The `uuid` field is missing in `metadata.json`'))
            self.uuid = self.metadata['uuid']
        except InvalidExtensionData as ex:
            raise serializers.ValidationError(ex.message)

        return value

    def validate_shell_license_compliant(self, value):
        if not value:
            raise serializers.ValidationError(_("Extension can not be published without grant to use it with GNOME Shell compatible license"))

        return value

    def validate_tos_compliant(self, value):
        if not value:
            raise serializers.ValidationError(
                _("Extension can not be published without grant to change extension maintainer")
            )

        return value

    def create(self, validated_data):
        with transaction.atomic():
            try:
                extension = models.Extension.objects.get(uuid=self.uuid)
            except models.Extension.DoesNotExist:
                extension = models.Extension(creator=validated_data['user'])

            assert validated_data['user'] == extension.creator or validated_data['user'].is_superuser, (
                _("An extension with that UUID has already been added")
            )

            extension.parse_metadata_json(self.metadata)
            extension.save()

            try:
                extension.full_clean()
            except ValidationError as e:
                raise serializers.ValidationError(e.messages)

            version = models.ExtensionVersion.objects.create(extension=extension,
                                                             source=validated_data['source'],
                                                             status=models.STATUS_UNREVIEWED)
            version.parse_metadata_json(self.metadata)
            version.replace_metadata_json()
            version.save()

            models.submitted_for_review.send(sender=validated_data['user'], version=version)

            return version

    def to_representation(self, instance):
        serializer = ExtensionVersionSerializer(instance=instance)
        return serializer.data
