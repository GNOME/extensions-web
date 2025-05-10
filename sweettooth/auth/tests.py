# SPDX-License-Identifer: AGPL-3.0-or-later

import re

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core import mail
from django.test.testcases import TestCase
from django.urls import reverse
from django_registration import validators
from rest_framework import status
from rest_framework.test import APIRequestFactory, APITestCase
from rest_registration.api.views import login, register

from . import views
from .forms import AutoFocusRegistrationForm, ProfileForm, RegistrationForm
from .serializers import RegisterUserSerializer
from .urls import PASSWORD_RESET_TOKEN_PATTERN

User = get_user_model()


class RegistrationDataTest(TestCase):
    registration_data = {
        User.USERNAME_FIELD: "bob",
        "email": "bob@example.com",
        "password": "mysecretpassword",
    }
    valid_data = {
        User.USERNAME_FIELD: "alice",
        "email": "alice@example.com",
        "password1": "swordfish",
        "password2": "swordfish",
    }

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.registered_user = User.objects.create_user(
            username=cls.registration_data[User.USERNAME_FIELD],
            email=cls.registration_data["email"],
            password=cls.registration_data["password"],
        )


# registration/tests/test_forms.py
class AuthTests(RegistrationDataTest):
    def test_email_uniqueness(self):
        data = self.valid_data.copy()
        data.update(email=self.registration_data["email"])
        form = AutoFocusRegistrationForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["email"], [str(validators.DUPLICATE_EMAIL)])

        form = AutoFocusRegistrationForm(data=self.valid_data.copy())
        self.assertTrue(form.is_valid())

    def test_auth_username_email(self):
        self.assertTrue(
            self.client.login(
                username=self.registration_data[User.USERNAME_FIELD],
                password=self.registration_data["password"],
            )
        )

        self.assertTrue(
            self.client.login(
                username=self.registration_data["email"],
                password=self.registration_data["password"],
            )
        )

        self.assertFalse(
            self.client.login(
                username=self.registration_data[User.USERNAME_FIELD],
                password=self.valid_data["password1"],
            )
        )

        self.assertFalse(
            self.client.login(
                username=self.registration_data["email"],
                password=self.valid_data["password1"],
            )
        )

    def test_auth_disallowed_username(self):
        with self.settings(
            DISALLOWED_USERNAMES=(self.registration_data[User.USERNAME_FIELD],)
        ):
            self.assertFalse(
                self.client.login(
                    username=self.registration_data[User.USERNAME_FIELD],
                    password=self.registration_data["password"],
                )
            )


class RegistrationTests(RegistrationDataTest):
    def test_username_email(self):
        form = RegistrationForm(data=self.valid_data)
        self.assertTrue(form.is_valid())

        data = self.valid_data.copy()
        data[User.USERNAME_FIELD] = data["email"]
        form = RegistrationForm(data=data)
        self.assertFalse(form.is_valid())

    def test_username_case(self):
        data = self.valid_data.copy()
        data[User.USERNAME_FIELD] = self.registration_data[
            User.USERNAME_FIELD
        ].swapcase()
        self.assertTrue(
            data[User.USERNAME_FIELD] != self.registration_data[User.USERNAME_FIELD]
        )

        form = RegistrationForm(data=data)
        self.assertFalse(form.is_valid())

    def test_disallowed(self):
        with self.settings(DISALLOWED_USERNAMES=("gnome",)):
            data = self.valid_data.copy()
            data[User.USERNAME_FIELD] = "official_GNOME"

            form = RegistrationForm(data=data)
            self.assertFalse(form.is_valid())


class PasswordResetTests(RegistrationDataTest):
    def test_reset_token_pattern(self):
        token = PasswordResetTokenGenerator().make_token(self.registered_user)
        pattern = re.compile(f"^{PASSWORD_RESET_TOKEN_PATTERN}$")

        self.assertTrue(pattern.match(token))


class SettingsTest(TestCase):
    registration_data = [
        {
            User.USERNAME_FIELD: "bob",
            "email": "bob@example.com",
            "password": "mysecretpassword",
        },
        {
            User.USERNAME_FIELD: "alice",
            "email": "alice@example.com",
            "password": "swordfish",
        },
    ]
    registered_users = []

    valid_data = {
        User.USERNAME_FIELD: "username",
        "email": "some@example.com",
        "email2": "some2@example.com",
        "password": "P@ssw0rd",
    }

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        for data in cls.registration_data:
            cls.registered_users.append(
                User.objects.create_user(
                    username=data[User.USERNAME_FIELD],
                    email=data["email"],
                    password=data["password"],
                )
            )

    # Copied from the Django 3.2.25 assertFormError which was changed in the 5.0
    # https://github.com/django/django/blob/3.2.25/django/test/testcases.py#L484
    def assertResponseFormError(self, response, form, field, errors, msg_prefix=""):
        def to_list(value):
            """
            Put value into a list if it's not already one. Return an empty list if
            value is None.
            """
            if value is None:
                value = []
            elif not isinstance(value, list):
                value = [value]
            return value

        """
        Assert that a form used to render the response has a specific field
        error.
        """
        if msg_prefix:
            msg_prefix += ": "

        # Put context(s) into a list to simplify processing.
        contexts = to_list(response.context)
        if not contexts:
            self.fail(
                msg_prefix + "Response did not use any contexts to render the response"
            )

        # Put error(s) into a list to simplify processing.
        errors = to_list(errors)

        # Search all contexts for the error.
        found_form = False
        for i, context in enumerate(contexts):
            if form not in context:
                continue
            found_form = True
            for err in errors:
                if field:
                    if field in context[form].errors:
                        field_errors = context[form].errors[field]
                        self.assertTrue(
                            err in field_errors,
                            msg_prefix + "The field '%s' on form '%s' in"
                            " context %d does not contain the error '%s'"
                            " (actual errors: %s)"
                            % (field, form, i, err, repr(field_errors)),
                        )
                    elif field in context[form].fields:
                        self.fail(
                            msg_prefix
                            + (
                                "The field '%s' on form '%s' in context %d"
                                " contains no errors"
                            )
                            % (field, form, i)
                        )
                    else:
                        self.fail(
                            msg_prefix
                            + (
                                "The form '%s' in context %d "
                                "does not contain the field '%s'"
                            )
                            % (form, i, field)
                        )
                else:
                    non_field_errors = context[form].non_field_errors()
                    self.assertTrue(
                        err in non_field_errors,
                        msg_prefix + "The form '%s' in context %d does not"
                        " contain the non-field error '%s'"
                        " (actual errors: %s)"
                        % (form, i, err, non_field_errors or "none"),
                    )
        if not found_form:
            self.fail(
                msg_prefix + "The form '%s' was not used to render the response" % form
            )

    def test_settings_view(self):
        self.client.force_login(self.registered_users[0])

        response = self.client.post(
            reverse("auth-settings"),
            {
                "profile_form": True,
                "username": self.valid_data[User.USERNAME_FIELD],
                "email": self.registered_users[0].email,
                "display_name": self.registered_users[0].display_name,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, views.SettingsView.MESSAGE_PROFILE_SAVED)

        response = self.client.post(
            reverse("auth-settings"),
            {
                "profile_form": True,
                "username": getattr(self.registered_users[1], User.USERNAME_FIELD),
                "email": self.registered_users[0].email,
                "display_name": self.registered_users[0].display_name,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertResponseFormError(
            response, "profile_form", "username", validators.DUPLICATE_USERNAME
        )

        response = self.client.post(
            reverse("auth-settings"),
            {
                "profile_form": True,
                "username": self.valid_data[User.USERNAME_FIELD],
                "email": self.registered_users[1].email,
                "display_name": self.registered_users[0].display_name,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertResponseFormError(
            response, "profile_form", "email", validators.DUPLICATE_EMAIL
        )

        response = self.client.post(
            reverse("auth-settings"),
            {
                "profile_form": True,
                "username": self.valid_data[User.USERNAME_FIELD],
                "email": self.valid_data["email"],
                "display_name": self.registered_users[0].display_name,
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("to confirm your new email", mail.outbox[0].body)
        self.assertIn("reset your password and email", mail.outbox[1].body)

        response = self.client.post(
            reverse("auth-settings"),
            {
                "profile_form": True,
                "username": self.valid_data[User.USERNAME_FIELD],
                "email": self.valid_data["email2"],
                "display_name": self.registered_users[0].display_name,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertResponseFormError(
            response, "profile_form", "email", ProfileForm.MESSAGE_EMAIL_TOO_FAST
        )

    def test_disallowed_name(self):
        with self.settings(DISALLOWED_USERNAMES=("gnome",)):
            data = self.valid_data.copy()
            data[User.USERNAME_FIELD] = "official_GNOME"

            form = ProfileForm(data=data)
            self.assertFalse(form.is_valid())

            data = self.valid_data.copy()
            data["display_name"] = "official_GNOME"

            form = ProfileForm(data=data)
            self.assertFalse(form.is_valid())


class APIRegistrationDataTest(RegistrationDataTest, APITestCase):
    valid_data = {
        User.USERNAME_FIELD: "alice",
        "email": "alice@example.com",
        "password": "swordfish",
        "password_confirm": "swordfish",
        "display_name": "Alice",
    }

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = APIRequestFactory()


# registration/tests/test_forms.py
class APIAuthTests(APIRegistrationDataTest):
    def test_email_uniqueness(self):
        url = reverse("rest_registration:register")

        data = self.valid_data.copy()
        data.update(email=self.registration_data["email"])

        request = self.factory.post(url, data)
        response = register(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data.keys())

    # TODO: make email DB field unique and enable email login
    def test_auth_username_email(self):
        url = reverse("rest_registration:login")

        response = login(
            self.factory.post(
                url,
                {
                    "login": self.registration_data[User.USERNAME_FIELD],
                    "password": self.registration_data["password"],
                },
            )
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = login(
            self.factory.post(
                url,
                {
                    "login": self.registration_data["email"],
                    "password": self.registration_data["password"],
                },
            )
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = login(
            self.factory.post(
                url,
                {
                    "login": self.registration_data[User.USERNAME_FIELD],
                    "password": self.valid_data["password"],
                },
            )
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = login(
            self.factory.post(
                url,
                {
                    "login": self.registration_data["email"],
                    "password": self.valid_data["password"],
                },
            )
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class APIRegistrationTests(APIRegistrationDataTest):
    def test_username_email(self):
        serializer = RegisterUserSerializer(data=self.valid_data.copy())
        self.assertTrue(serializer.is_valid())

        data = self.valid_data.copy()
        data[User.USERNAME_FIELD] = data["email"]
        serializer = RegisterUserSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_username_case(self):
        url = reverse("rest_registration:register")

        data = self.valid_data.copy()
        data[User.USERNAME_FIELD] = self.registration_data[
            User.USERNAME_FIELD
        ].swapcase()
        self.assertTrue(
            data[User.USERNAME_FIELD] != self.registration_data[User.USERNAME_FIELD]
        )

        request = self.factory.post(url, data)
        response = register(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
