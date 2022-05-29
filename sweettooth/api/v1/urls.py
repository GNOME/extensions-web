"""
    GNOME Shell extensions repository
    Copyright (C) 2020  Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""

from django.urls import path

from rest_framework.routers import SimpleRouter

from sweettooth.api.v1.views import HelloView
from sweettooth.users.views import UserProfileDetailView

urlpatterns = [
    path('v1/hello/', HelloView.as_view()),
    path('v1/profile/<int:pk>/',
         UserProfileDetailView.as_view(),
         name='userprofile-detail'),
]
