# SPDX-License-Identifer: AGPL-3.0-or-later

from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_registration.api.serializers import DefaultRegisterUserSerializer
from rest_registration.utils.users import get_user_email_field_name

User = get_user_model()


def user_with_email_exists(email: str) -> bool:
    email_field_name = get_user_email_field_name()

    if not email_field_name:
        return True

    queryset = User.objects.filter(**{f"{email_field_name}__iexact": email})
    return queryset.exists()


def user_with_username_exists(username: str) -> bool:
    return User.objects.filter(username__iexact=username).exists()


class UserSerializer(serializers.ModelSerializer):
    avatar = serializers.CharField(read_only=True)
    is_authenticated = serializers.SerializerMethodField()

    def get_is_authenticated(self, data):
        return data.is_authenticated

    class Meta:
        model = get_user_model()
        fields = "__all__"
        extra_kwargs = {"password": {"write_only": True}}


class RegisterUserSerializer(DefaultRegisterUserSerializer):
    def validate_email(self, value):
        if user_with_email_exists(value):
            raise serializers.ValidationError(_("This email is already registered"))

        return value

    def validate_username(self, value):
        if user_with_username_exists(value):
            raise serializers.ValidationError(_("This username is already registered"))

        return value

    def validate(self, attrs):
        if attrs["username"].lower() == attrs["email"].lower():
            raise serializers.ValidationError(_("You should not use email as username"))

        return super().validate(attrs)
