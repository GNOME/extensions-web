
from django import forms
from django.contrib.auth import forms as auth_forms
from django.utils.translation import ugettext_lazy as _
from django_registration.forms import RegistrationFormCaseInsensitive, RegistrationFormUniqueEmail

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

class LoginOrEmailAuthenticationForm(object):
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
                               InlineForm, LoginOrEmailAuthenticationForm, auth_forms.AuthenticationForm):
    pass

class AuthenticationForm(LoginOrEmailAuthenticationForm, AutoFocusForm,
                        auth_forms.AuthenticationForm):
    pass

class RegistrationForm(RegistrationFormCaseInsensitive, RegistrationFormUniqueEmail):
    # Copies the standard setting from the django.contrib.auth.forms
    username = forms.RegexField(label=_("Username"), max_length=30, regex=r'^[\w.@+-]+$',
        help_text = _("Required. 30 characters or fewer. Letters, digits and @/./+/-/_ only."),
        error_messages = {'invalid': _("This value may contain only letters, numbers and @/./+/-/_ characters.")})
    email = forms.EmailField(widget=forms.TextInput(attrs=dict(maxlength=75)),
                             label=_(u'Email'))


class AutoFocusRegistrationForm(AutoFocusForm, RegistrationForm):
    pass
