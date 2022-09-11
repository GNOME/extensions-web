"""
    GNOME Shell extensions repository
    Copyright (C) 2020  Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""

from django.urls import include, path

from rest_framework.routers import SimpleRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from sweettooth.api.v1.views import HelloView
from sweettooth.extensions.views import ExtensionsViewSet, ExtensionsVersionsViewSet
from sweettooth.users.views import UserProfileDetailView

# Create a router and register our viewsets with it.
router = SimpleRouter()
router.register(
    r'v1/extensions',
    ExtensionsViewSet,
    basename='extension',
)
router.register(
    r'v1/extensions-versions',
    ExtensionsVersionsViewSet,
    basename='extensions-versions',
)

urlpatterns = router.urls
urlpatterns += [
    path('v1/accounts/', include('rest_registration.api.urls')),

    path('v1/hello/', HelloView.as_view()),
    path('v1/profile/<int:pk>/',
         UserProfileDetailView.as_view(),
         name='userprofile-detail'),

    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
