# SPDX-License-Identifer: AGPL-3.0-or-later

from django.conf import settings
from django.contrib.auth.backends import ModelBackend, UserModel


class LoginEmailAuthentication(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        user = super().authenticate(
            request, username=username, password=password, **kwargs
        )
        if user is not None:
            return user

        if username is not None:
            try:
                user = UserModel.objects.get(email=username)
            except UserModel.DoesNotExist:
                # Run the default password hasher once to reduce the timing
                # difference between an existing and a nonexistent user (#20760).
                UserModel().set_password(password)
            else:
                if user.check_password(password) and self.user_can_authenticate(user):
                    return user

    def user_can_authenticate(self, user) -> bool:
        if settings.DISALLOWED_USERNAMES:
            if any(
                word.lower() in user.get_username().lower()
                for word in settings.DISALLOWED_USERNAMES
            ):
                return False

        return super().user_can_authenticate(user)
