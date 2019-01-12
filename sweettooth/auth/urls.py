
from django.views.generic.base import TemplateView
from django.conf.urls import url, include
from django.contrib.auth import views as auth_views
from sweettooth.auth import views, forms
from registration.backends.model_activation.views import RegistrationView

urlpatterns = [
    url(r'^login/', auth_views.login,
        dict(template_name='registration/login.html',
             authentication_form=forms.AuthenticationForm), name='auth-login'),

    url(r'^change_display_name/(?P<pk>\d+)', views.ajax_change_display_name),

    url(r'^logout/', auth_views.logout,
        dict(next_page='/'), name='auth-logout'),

    url(r'^register/$', RegistrationView.as_view(form_class=forms.AutoFocusRegistrationForm),
        name='registration_register'),

    url(r'settings/(?P<user>.+)', TemplateView.as_view(template_name='registration/settings.html'),
        name='auth-settings'),

    url(r'', include('registration.backends.model_activation.urls')),
    url(r'^profile/(?P<user>.+)', views.profile, name='auth-profile'),
    url(r'^profile/', views.profile_redirect, name='auth-profile'),
]
