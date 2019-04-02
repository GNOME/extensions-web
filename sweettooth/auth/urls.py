
from django.views.generic.base import TemplateView
from django.conf.urls import url, include
from django_registration.views import RegistrationView
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from sweettooth.auth import views, forms

urlpatterns = [
    url(r'^login/', LoginView.as_view(form_class=forms.AuthenticationForm), name='auth-login'),

    url(r'^change_display_name/(?P<pk>\d+)', views.ajax_change_display_name),

    url(r'^logout/', LogoutView.as_view(next_page='/'), name='auth-logout'),

    url(r'^register/$', RegistrationView.as_view(form_class=forms.AutoFocusRegistrationForm),
        name='registration_register'),

    url(r'settings/(?P<user>.+)', TemplateView.as_view(template_name='profile/settings.html'),
        name='auth-settings'),

    url(r'', include('django_registration.backends.activation.urls')),
    url(r'^profile/(?P<user>.+)', views.profile, name='auth-profile'),
    url(r'^profile/', views.profile_redirect, name='auth-profile'),

    url(r'^login/$',
        auth_views.LoginView.as_view(),
        name='auth-login'),
    url(r'^logout/$',
        auth_views.LogoutView.as_view(),
        name='auth-logout'),
    url(r'^password/change/$',
        auth_views.PasswordChangeView.as_view(),
        name='password_change'),
    url(r'^password/change/done/$',
        auth_views.PasswordChangeDoneView.as_view(),
        name='password_change_done'),
    url(r'^password/reset/$',
        auth_views.PasswordResetView.as_view(
            email_template_name='registration/password_reset_email.txt'
        ),
        name='password_reset'),
    url(r'^password/reset/complete/$',
        auth_views.PasswordResetCompleteView.as_view(),
        name='password_reset_complete'),
    url(r'^password/reset/done/$',
        auth_views.PasswordResetDoneView.as_view(),
        name='password_reset_done'),
    url(r'^password/reset/confirm/(?P<uidb64>[0-9A-Za-z_\-]+)/'
        r'(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$',
        auth_views.PasswordResetConfirmView.as_view(),
        name='password_reset_confirm'),
]
