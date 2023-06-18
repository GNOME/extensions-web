from datetime import datetime, timedelta
import re
from typing import Any, Optional
from django import forms
from django.conf import settings
from django.contrib.auth import forms as auth_forms, get_user_model
from django.utils.translation import gettext_lazy as _
from django_registration.forms import (
    RegistrationForm as BaseRegistrationForm,
    RegistrationFormCaseInsensitive,
    RegistrationFormUniqueEmail
)
from django_registration import validators


User = get_user_model()


class PlainOutputForm(object):
    def as_plain(self):
        return self._html_output(
            normal_row = u'<div class="form-group">%(field)s</div> %(errors)s%(help_text)s',
            error_row = u'%s',
            row_ender = u'</div>',
            help_text_html = u'<br /><span class="helptext">%s</span>',
            errors_on_separate_row = False)


class AutoFocusForm(object):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        for field in self.fields:
            self.fields[field].widget.attrs['autofocus'] = 'autofocus'
            break


class LoginOrEmailAuthenticationForm(auth_forms.AuthenticationForm):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields['username'].label = _('Username or email')


class InlineForm(object):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        for field in self.fields.values():
            field.widget.attrs['placeholder'] = field.label
            field.widget.attrs['class'] = 'form-control'


class InlineAuthenticationForm(PlainOutputForm, AutoFocusForm,
                               InlineForm, LoginOrEmailAuthenticationForm):
    pass


class AuthenticationForm(AutoFocusForm, LoginOrEmailAuthenticationForm):
    pass


class BaseProfileForm(forms.Form):
    # Copies the standard setting from the django.contrib.auth.forms
    username = forms.RegexField(
        label=_("Username"), max_length=30, regex=r'^[\w.@+-]+$',
        help_text=_("Required. 30 characters or fewer. Letters, digits and @/./+/-/_ only."),
        error_messages={'invalid': _("This value may contain only letters, numbers and @/./+/-/_ characters.")}
    )
    email = forms.EmailField(
        label=_(u'Email')
    )

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get(User.USERNAME_FIELD)

        if username == cleaned_data.get('email'):
            raise forms.ValidationError(_("You should not use email as username"))

        if settings.DISALLOWED_USERNAMES and username:
            if any(
                word.lower() in username.lower()
                for word in settings.DISALLOWED_USERNAMES
            ):
                raise forms.ValidationError(_("Your username contains forbidden words"))

        return cleaned_data


class RegistrationForm(BaseProfileForm, RegistrationFormCaseInsensitive, RegistrationFormUniqueEmail):
    class Meta(BaseRegistrationForm.Meta):
        model = User


class AutoFocusRegistrationForm(AutoFocusForm, RegistrationForm):
    pass


class ProfileForm(BaseProfileForm, forms.ModelForm):
    class Meta:
        model = User
        fields = ('username', 'display_name', 'email')

    profile_form = forms.BooleanField(widget=forms.HiddenInput(), initial=True)
    display_name = forms.RegexField(
        regex=re.compile(r'^[\w.@+\- ]+$', re.UNICODE),
        max_length=64,
        required=False,
    )

    field_order = Meta.fields

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        email_field = User.get_email_field_name()
        if hasattr(self, "reserved_names"):
            reserved_names = self.reserved_names
        else:
            reserved_names = validators.DEFAULT_RESERVED_NAMES
        username_validators = [
            validators.ReservedNameValidator(reserved_names),
            validators.validate_confusables,
        ]
        self.fields[User.USERNAME_FIELD].validators.extend(username_validators)
        self.fields[email_field].validators.extend(
            (validators.HTML5EmailValidator(), validators.validate_confusables_email)
        )
        self.fields[email_field].required = True

    def clean_username(self):
        if (
            User.objects
                .filter(**{f'{User.USERNAME_FIELD}__iexact': self.cleaned_data[User.USERNAME_FIELD]})
                .exclude(pk=self.instance.pk).exists()
        ):
            raise forms.ValidationError(validators.DUPLICATE_USERNAME, code="unique")

        return self.cleaned_data[User.USERNAME_FIELD]

    def clean_email(self):
        if (
            User.objects
                .filter(**{'email__iexact': self.cleaned_data['email']})
                .exclude(pk=self.instance.pk).exists()
        ):
            raise forms.ValidationError(validators.DUPLICATE_EMAIL, code="unique")

        if (
            self.cleaned_data['email'] != self.instance.email and
            self.instance.last_email_change and
            datetime.now() - self.instance.last_email_change < timedelta(days=7)
        ):
            raise forms.ValidationError(_("You cannot change your email more than once every 7 days"), code="fast")

        return self.cleaned_data['email']


class DeleteAccountForm(forms.Form):
    delete_form = forms.BooleanField(widget=forms.HiddenInput(), initial=True)
    delete_account = forms.TypedChoiceField(
        label=_("Delete my account"),
        help_text=_("Your account will be deleted in 7 days"),
        coerce=lambda x: x == 'True',
        choices=((True, _('Yes')), (False, _('No'))),
        widget=forms.RadioSelect,
    )
    current_password = forms.CharField(
        label=_("Current password"),
        help_text=_("You don't need to specify a password to cancel account removal"),
        widget=forms.PasswordInput,
        required=False,
        strip=False,
    )
