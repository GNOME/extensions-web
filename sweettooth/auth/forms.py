import re
from datetime import datetime, timedelta
from typing import Any

from django import forms
from django.conf import settings
from django.contrib.auth import forms as auth_forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django_registration import validators
from django_registration.forms import RegistrationForm as BaseRegistrationForm
from django_registration.forms import (
    RegistrationFormCaseInsensitive,
    RegistrationFormUniqueEmail,
)

User = get_user_model()


class AutoFocusForm:
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        for field in self.fields:
            self.fields[field].widget.attrs["autofocus"] = "autofocus"
            break


class LoginOrEmailAuthenticationForm(auth_forms.AuthenticationForm):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["username"].label = _("Username or email")

    def clean(self) -> dict[str, Any]:
        try:
            return super().clean()
        except User.MultipleObjectsReturned:
            raise forms.ValidationError(
                _(
                    "You have multiple accounts registered using single email. You can"
                    " log in using your username or you can request removal of"
                    " duplicate accounts using GNOME Gitlab (%(url)s)."
                )
                % {
                    "url": "https://gitlab.gnome.org/Infrastructure/extensions-web/-/issues"  # noqa: E501
                }
            )


class InlineForm:
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        for field in self.fields.values():
            field.widget.attrs["placeholder"] = field.label
            field.widget.attrs["class"] = "form-control"


class InlineAuthenticationForm(
    AutoFocusForm, InlineForm, LoginOrEmailAuthenticationForm
):
    pass


class AuthenticationForm(AutoFocusForm, LoginOrEmailAuthenticationForm):
    pass


class BaseProfileForm(forms.Form):
    # Copies the standard setting from the django.contrib.auth.forms
    username = forms.RegexField(
        label=_("Username"),
        max_length=30,
        regex=r"^[\w.@+-]+$",
        help_text=_(
            "Required. 30 characters or fewer. Letters, digits and @/./+/-/_ only."
        ),
        error_messages={
            "invalid": _(
                "This value may contain only letters, numbers and @/./+/-/_ characters."
            )
        },
    )
    email = forms.EmailField(label=_("Email"))

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get(User.USERNAME_FIELD)

        if username == cleaned_data.get("email"):
            raise forms.ValidationError(_("You should not use email as username"))

        if self.is_disallowed_name(username):
            raise forms.ValidationError(_("Your username contains forbidden words"))

        return cleaned_data

    def is_disallowed_name(self, name: str):
        if settings.DISALLOWED_USERNAMES and name:
            if any(
                word.lower() in name.lower() for word in settings.DISALLOWED_USERNAMES
            ):
                return True

        return False


class RegistrationForm(
    BaseProfileForm, RegistrationFormCaseInsensitive, RegistrationFormUniqueEmail
):
    class Meta(BaseRegistrationForm.Meta):
        model = User


class AutoFocusRegistrationForm(AutoFocusForm, RegistrationForm):
    pass


class ProfileForm(BaseProfileForm, forms.ModelForm):
    class Meta:
        model = User
        fields = ("username", "display_name", "email")

    MESSAGE_EMAIL_TOO_FAST = _(
        "You cannot change your email more than once every 7 days"
    )

    profile_form = forms.BooleanField(widget=forms.HiddenInput(), initial=True)
    display_name = forms.RegexField(
        regex=re.compile(r"^[\w.@+\- ]+$", re.UNICODE),
        max_length=64,
        required=False,
    )

    field_order = Meta.fields

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.new_email = None

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

    def clean_display_name(self):
        if self.is_disallowed_name(self.cleaned_data["display_name"]):
            raise forms.ValidationError(_("Your display name contains forbidden words"))

        return self.cleaned_data["display_name"]

    def clean_username(self):
        if (
            User.objects.filter(
                **{
                    f"{User.USERNAME_FIELD}__iexact": self.cleaned_data[
                        User.USERNAME_FIELD
                    ]
                }
            )
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise forms.ValidationError(validators.DUPLICATE_USERNAME, code="unique")

        return self.cleaned_data[User.USERNAME_FIELD]

    def clean_email(self):
        if (
            User.objects.filter(**{"email__iexact": self.cleaned_data["email"]})
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise forms.ValidationError(validators.DUPLICATE_EMAIL, code="unique")

        if self.cleaned_data["email"] != self.instance.email:
            if (
                self.instance.last_email_change
                and datetime.now() - self.instance.last_email_change < timedelta(days=7)
            ):
                raise forms.ValidationError(self.MESSAGE_EMAIL_TOO_FAST, code="fast")

            self.new_email = self.cleaned_data["email"]
            return self.instance.email

        return self.cleaned_data["email"]


class DeleteAccountForm(forms.Form):
    delete_form = forms.BooleanField(widget=forms.HiddenInput(), initial=True)
    delete_account = forms.TypedChoiceField(
        label=_("Delete my account"),
        help_text=_("Your account will be deleted in 7 days"),
        coerce=lambda x: x == "True",
        choices=((True, _("Yes")), (False, _("No"))),
        widget=forms.RadioSelect,
    )
    current_password = forms.CharField(
        label=_("Current password"),
        help_text=_("You don't need to specify a password to cancel account removal"),
        widget=forms.PasswordInput,
        required=False,
        strip=False,
    )
