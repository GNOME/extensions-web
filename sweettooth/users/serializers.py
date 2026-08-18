# SPDX-License-Identifer: AGPL-3.0-or-later

from django.contrib.auth import get_user_model
from rest_framework import serializers


class BaseUserProfileSerializer(serializers.ModelSerializer):
    avatar = serializers.CharField(read_only=True)
    display_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = get_user_model()
        fields = ["id", "username", "avatar", "display_name"]


class UserProfileSerializer(BaseUserProfileSerializer):
    extensions = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta(BaseUserProfileSerializer.Meta):
        fields = BaseUserProfileSerializer.Meta.fields + ["extensions"]
