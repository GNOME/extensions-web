# SPDX-License-Identifer: AGPL-3.0-or-later

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from sweettooth.extensions.models import (
    Extension,
    ExtensionVersion,
    InvalidExtensionData,
    ShellVersion,
)
from sweettooth.users.serializers import BaseUserProfileSerializer

from . import models


class ShellVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShellVersion
        fields = [
            "major",
            "minor",
            "point",
        ]


class ExtensionSerializer(serializers.ModelSerializer):
    creator = BaseUserProfileSerializer(many=False, read_only=True)
    donation_urls = serializers.SerializerMethodField()
    link = serializers.CharField(source="get_absolute_url", read_only=True)

    class Meta:
        model = Extension
        fields = [
            "id",
            "uuid",
            "name",
            "creator",
            "description",
            "created",
            "updated",
            "downloads",
            "popularity",
            "screenshot",
            "icon",
            "rating",
            "rated",
            "url",
            "donation_urls",
            "link",
        ]

    def get_donation_urls(self, obj):
        return [donation.full_url for donation in obj.donation_urls.all()]


class ExtensionVersionSerializer(serializers.ModelSerializer):
    # TODO: change primary key to UUID
    extension = serializers.SlugRelatedField(
        many=False, read_only=True, slug_field="uuid"
    )
    shell_versions = ShellVersionSerializer(many=True, read_only=True)

    class Meta:
        model = ExtensionVersion
        fields = [
            "extension",
            "version",
            "version_name",
            "status",
            "shell_versions",
            "created",
            "session_modes",
        ]


class InstalledExtensionSerializer(serializers.Serializer):
    version = serializers.CharField(allow_blank=True, default="0")


class ExtensionsUpdatesSerializer(serializers.Serializer):
    installed = serializers.DictField(child=InstalledExtensionSerializer())
    shell_version = serializers.CharField()
    version_validation_enabled = serializers.BooleanField(default=False)


class ExtensionUploadSerializer(serializers.Serializer):
    TOS_VALIDATION_ERROR = _(
        "You must agree with the extensions.gnome.org terms of service"
    )

    source = serializers.FileField(required=True)
    shell_license_compliant = serializers.BooleanField(
        required=True,
        label=_(
            "By uploading this extension I agree and verify that in any controversial"
            " case regarding the compatibility of extension's license with the GNOME"
            " Shell's license, the extension uploaded by me may be used by any GNOME"
            " Shell user under the terms of the license used by GNOME Shell"
        ),
    )
    tos_compliant = serializers.BooleanField(
        required=True,
        label=_(
            "I agree that a staff of extensions.gnome.org website may remove, modify or"
            " reassign maintainership of the extension uploaded by me"
        ),
    )

    def validate_source(self, value):
        try:
            self.metadata = models.parse_zipfile_metadata(value)
            if "uuid" not in self.metadata:
                raise serializers.ValidationError(
                    _("The `uuid` field is missing in `metadata.json`")
                )
            self.uuid = self.metadata["uuid"]
        except InvalidExtensionData as ex:
            raise serializers.ValidationError(ex.message) from ex

        return value

    def validate_shell_license_compliant(self, value):
        if not value:
            raise serializers.ValidationError(self.TOS_VALIDATION_ERROR)

        return value

    def validate_tos_compliant(self, value):
        if not value:
            raise serializers.ValidationError(self.TOS_VALIDATION_ERROR)

        return value

    def create(self, validated_data):
        if "user" not in validated_data:
            raise Exception("Serializer was called without passing `user` instance")

        with transaction.atomic():
            try:
                try:
                    extension = models.Extension.objects.get(uuid=self.uuid)
                    extension.update_from_metadata(self.metadata)
                except models.Extension.DoesNotExist:
                    extension = models.Extension(
                        creator=validated_data["user"], metadata=self.metadata
                    )
                else:
                    if (
                        validated_data["user"] != extension.creator
                        and not validated_data["user"].is_superuser
                    ):
                        raise serializers.ValidationError(
                            _("An extension with that UUID has already been added")
                        )

                extension.full_clean()
            except ValidationError as e:
                raise serializers.ValidationError(e.messages)

            extension.save()

            if "version-name" in self.metadata:
                version_name = self.metadata.pop("version-name").strip()
            else:
                version_name = None

            version = models.ExtensionVersion(
                extension=extension,
                metadata=self.metadata,
                source=validated_data["source"],
                status=models.STATUS_UNREVIEWED,
                version_name=version_name,
            )

            try:
                version.full_clean()
            except ValidationError as e:
                raise serializers.ValidationError(e.messages)
            version.save()

            models.submitted_for_review.send(
                sender=validated_data["user"],
                request=validated_data["request"],
                version=version,
            )

            return version

    def to_representation(self, instance):
        serializer = ExtensionVersionSerializer(instance=instance)
        return serializer.data
