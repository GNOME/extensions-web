
from django import forms
from django.contrib.auth import forms as auth_forms
from django.utils.translation import ugettext_lazy as _
from registration.forms import RegistrationFormUniqueEmail

class PlainOutputForm(object):
    def as_plain(self):
        return self._html_output(
            normal_row = u'%(errors)s%(field)s%(help_text)s',
            error_row = u'%s',
            row_ender = u'',
            help_text_html = u'<br /><span class="helptext">%s</span>',
            errors_on_separate_row = False)

class AutoFocusForm(object):
    def __init__(self, *a, **kw):
        super(AutoFocusForm, self).__init__(*a, **kw)
        for field in self.fields:
            self.fields[field].widget.attrs['autofocus'] = 'autofocus'
            break

class InlineForm(object):
    def __init__(self, *a, **kw):
        super(InlineForm, self).__init__(*a, **kw)
        for field in self.fields.itervalues():
            field.widget.attrs['placeholder'] = field.label

class InlineAuthenticationForm(PlainOutputForm, AutoFocusForm,
                               InlineForm, auth_forms.AuthenticationForm):
    pass

class AuthenticationForm(AutoFocusForm, auth_forms.AuthenticationForm):
    pass

class RegistrationForm(RegistrationFormUniqueEmail):
    # Copies the standard setting from the django.contrib.auth.forms
    username = forms.RegexField(label=_("Username"), max_length=30, regex=r'^[\w.@+-]+$',
        help_text = _("Required. 30 characters or fewer. Letters, digits and @/./+/-/_ only."),
        error_messages = {'invalid': _("This value may contain only letters, numbers and @/./+/-/_ characters.")})
    email = forms.EmailField(widget=forms.TextInput(attrs=dict(maxlength=75)),
                             label=_(u'Email'))
    password1 = forms.CharField(label=_("Password"), widget=forms.PasswordInput)
    password2 = forms.CharField(label=_("Password confirmation"), widget=forms.PasswordInput,
        help_text = _("Enter the same password as above, for verification."))


class AutoFocusRegistrationForm(AutoFocusForm, RegistrationForm):
    pass
