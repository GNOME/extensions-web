from collections.abc import Sequence
from typing import TYPE_CHECKING

from django.http import HttpRequest
from drf_spectacular.authentication import TokenScheme
from drf_spectacular.plumbing import build_bearer_security_scheme_object
from knox.auth import AuthToken, TokenAuthentication
from knox.settings import knox_settings
from knox.views import LoginView
from rest_framework.authentication import BaseAuthentication
from rest_registration.auth_token_managers import AbstractAuthTokenManager
from rest_registration.auth_token_managers import AuthToken as AuthTokenType

if TYPE_CHECKING:
    from django.contrib.auth.base_user import AbstractBaseUser


class KnoxTokenScheme(TokenScheme):
    target_class = "knox.auth.TokenAuthentication"

    def get_security_definition(self, auto_schema):
        return build_bearer_security_scheme_object(
            header_name="Authorization",
            token_prefix=knox_settings.AUTH_HEADER_PREFIX,
        )


class KnoxAuthTokenManager(AbstractAuthTokenManager):
    def get_authentication_class(self) -> type[BaseAuthentication]:
        return TokenAuthentication

    def get_app_names(self) -> Sequence[str]:
        return [
            "knox",
        ]

    def provide_token(self, user: "AbstractBaseUser") -> AuthTokenType:
        request = HttpRequest()
        request.method = "POST"
        request.user = user
        request._force_auth_user = user

        token = LoginView.as_view()(request).data

        return AuthTokenType(token)

    def revoke_token(
        self, user: "AbstractBaseUser", *, token: AuthTokenType | None = None
    ) -> None:
        if token:
            AuthToken.objects.get(user=user, digest=token).delete()
        else:
            user.auth_token_set.all().delete()
