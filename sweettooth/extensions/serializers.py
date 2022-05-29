"""
    GNOME Shell extensions repository
    Copyright (C) 2020  Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""

from rest_framework import serializers

from sweettooth.extensions.models import Extension, ExtensionVersion, ShellVersion
from sweettooth.users.serializers import BaseUserProfileSerializer

class ShellVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShellVersion
        fields = [
            'major',
            'minor',
            'point',
        ]

class ExtensionVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtensionVersion
        fields = [
            'version',
            'status',
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
        ]
