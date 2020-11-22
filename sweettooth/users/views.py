"""
    GNOME Shell extensions repository
    Copyright (C) 2020  Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""

from django.contrib.auth import get_user_model

from rest_framework import generics
from rest_framework.response import Response

from sweettooth.users.serializers import UserProfileSerializer
from sweettooth.utils import gravatar_url

User = get_user_model()

class UserProfileDetailView(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserProfileSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.avatar = gravatar_url(None, instance.email)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
