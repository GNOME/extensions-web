from django.conf.urls import include
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import re_path
from django_registration.backends.activation.views import RegistrationView

from sweettooth.auth import forms, views

PASSWORD_RESET_TOKEN_PATTERN = r"[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,32}"

urlpatterns = [
    re_path(
        r"^login/",
        LoginView.as_view(form_class=forms.AuthenticationForm),
        name="auth-login",
    ),
    re_path(r"^logout/", LogoutView.as_view(next_page="/"), name="auth-logout"),
    re_path(
        r"^register/$",
        RegistrationView.as_view(form_class=forms.AutoFocusRegistrationForm),
        name="registration_register",
    ),
    re_path(r"settings", views.SettingsView.as_view(), name="auth-settings"),
    re_path(r"", include("django_registration.backends.activation.urls")),
    re_path(r"^profile/(?P<user>.+)", views.profile, name="auth-profile"),
    re_path(r"^profile/", views.profile_redirect, name="auth-profile"),
    re_path(r"^login/$", auth_views.LoginView.as_view(), name="auth-login"),
    re_path(r"^logout/$", auth_views.LogoutView.as_view(), name="auth-logout"),
    re_path(
        r"^password/change/$",
        auth_views.PasswordChangeView.as_view(),
        name="password_change",
    ),
    re_path(
        r"^password/change/done/$",
        auth_views.PasswordChangeDoneView.as_view(),
        name="password_change_done",
    ),
    re_path(
        r"^password/reset/$",
        auth_views.PasswordResetView.as_view(
            email_template_name="registration/password_reset_email.txt"
        ),
        name="password_reset",
    ),
    re_path(
        r"^password/reset/complete/$",
        auth_views.PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    re_path(
        r"^password/reset/done/$",
        auth_views.PasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    re_path(
        r"^password/reset/confirm/(?P<uidb64>[0-9A-Za-z_\-]+)/"
        rf"(?P<token>{PASSWORD_RESET_TOKEN_PATTERN})/$",
        auth_views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    re_path(
        r"^change-email/cancel/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z:_\-]+)",
        views.EmailChangeCancelView.as_view(),
        name="email_change_cancel",
    ),
    re_path(
        r"^change-email/confirm/(?P<user_id>\d+)/(?P<signature>[0-9A-Za-z:_-]+)",
        views.EmailChangeConfirmView.as_view(),
        name="email_change_confirm",
    ),
]
