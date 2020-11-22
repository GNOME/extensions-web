"""
    GNOME Shell extensions repository
    Copyright (C) 2020  Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""

from django.contrib.auth import get_user_model

from rest_framework import serializers


class BaseUserProfileSerializer(serializers.ModelSerializer):
    avatar = serializers.CharField(read_only=True)

    class Meta:
        model = get_user_model()
        fields = ['id', 'username', 'avatar']


class UserProfileSerializer(BaseUserProfileSerializer):
    extensions = serializers.PrimaryKeyRelatedField(
        many=True,
        read_only=True
    )

    class Meta(BaseUserProfileSerializer.Meta):
        fields = BaseUserProfileSerializer.Meta.fields + ['extensions']
