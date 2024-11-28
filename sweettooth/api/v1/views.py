# SPDX-License-Identifer: AGPL-3.0-or-later

from rest_framework.response import Response
from rest_framework.views import APIView

from sweettooth.auth import serializers
from sweettooth.utils import gravatar_url


class HelloView(APIView):
    def get(self, request, format=None):
        user = request.user
        user.avatar = (
            gravatar_url(None, user.email)
            if hasattr(user, "email") and user.email
            else None
        )

        return Response(
            {
                "user": serializers.UserSerializer(user).data,
            }
        )
