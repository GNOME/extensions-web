from django import forms
from django.conf import settings
from django.contrib.auth import forms as auth_forms, get_user_model
from django.utils.translation import gettext_lazy as _
from django_registration.forms import (
    RegistrationForm as BaseRegistrationForm,
    RegistrationFormCaseInsensitive,
    RegistrationFormUniqueEmail
)


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


class RegistrationForm(RegistrationFormCaseInsensitive, RegistrationFormUniqueEmail):
    class Meta(BaseRegistrationForm.Meta):
        model = get_user_model()

    # Copies the standard setting from the django.contrib.auth.forms
    username = forms.RegexField(label=_("Username"), max_length=30, regex=r'^[\w.@+-]+$',
        help_text = _("Required. 30 characters or fewer. Letters, digits and @/./+/-/_ only."),
        error_messages = {'invalid': _("This value may contain only letters, numbers and @/./+/-/_ characters.")})
    email = forms.EmailField(widget=forms.TextInput(attrs=dict(maxlength=75)),
                             label=_(u'Email'))

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get(get_user_model().USERNAME_FIELD)

        if username == cleaned_data.get('email'):
            raise forms.ValidationError(_("You should not use email as username"))

        if settings.DISALLOWED_USERNAMES and username:
            if any(
                word.lower() in username.lower()
                for word in settings.DISALLOWED_USERNAMES
            ):
                raise forms.ValidationError(_("Your username contains forbidden words"))

        return cleaned_data


class AutoFocusRegistrationForm(AutoFocusForm, RegistrationForm):
    pass


class DeleteAccountForm(forms.Form):
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
