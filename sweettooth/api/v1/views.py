"""
    GNOME Shell extensions repository
    Copyright (C) 2020  Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""
from rest_framework.response import Response
from rest_framework.views import APIView

from sweettooth.auth import serializers
from sweettooth.utils import gravatar_url


class HelloView(APIView):
    def get(self, request, format=None):
        user = request.user
        user.avatar = (
            gravatar_url(None, user.email)
            if hasattr(user, 'email') and user.email
            else None
        )

        return Response({
            'user': serializers.UserSerializer(user).data,
        })
