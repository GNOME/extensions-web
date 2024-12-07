# SPDX-License-Identifer: AGPL-3.0-or-later

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
