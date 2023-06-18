"""
    GNOME Shell extensions repository
    Copyright (C) 2016-2019  Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""

import re
from django.urls import reverse

from django_registration import validators

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.test.testcases import TestCase

from . import views
from .forms import AutoFocusRegistrationForm, RegistrationForm
from .urls import PASSWORD_RESET_TOKEN_PATTERN

User = get_user_model()


class RegistrationDataTest(TestCase):
    registration_data = {
        User.USERNAME_FIELD: 'bob',
        'email': 'bob@example.com',
        'password': 'mysecretpassword'
    }
    valid_data = {
        User.USERNAME_FIELD: 'alice',
        'email': 'alice@example.com',
        'password1': 'swordfish',
        'password2': 'swordfish',
    }

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.registered_user = User.objects.create_user(
            username=cls.registration_data[User.USERNAME_FIELD],
            email=cls.registration_data['email'],
            password=cls.registration_data['password']
        )


# registration/tests/test_forms.py
class AuthTests(RegistrationDataTest):
    def test_email_uniqueness(self):
        data = self.valid_data.copy()
        data.update(email=self.registration_data['email'])
        form = AutoFocusRegistrationForm(
            data=data
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors['email'],
            [str(validators.DUPLICATE_EMAIL)]
        )

        form = AutoFocusRegistrationForm(
            data=self.valid_data.copy()
        )
        self.assertTrue(form.is_valid())

    def test_auth_username_email(self):
        self.assertTrue(self.client.login(
            username=self.registration_data[User.USERNAME_FIELD],
            password=self.registration_data['password']))

        self.assertTrue(self.client.login(
            username=self.registration_data['email'],
            password=self.registration_data['password']))

        self.assertFalse(self.client.login(
            username=self.registration_data[User.USERNAME_FIELD],
            password=self.valid_data['password1']))

        self.assertFalse(self.client.login(
            username=self.registration_data['email'],
            password=self.valid_data['password1']))

    def test_auth_disallowed_username(self):
        with self.settings(DISALLOWED_USERNAMES=(self.registration_data[User.USERNAME_FIELD],)):
            self.assertFalse(self.client.login(
                    username=self.registration_data[User.USERNAME_FIELD],
                    password=self.registration_data['password']))


class RegistrationTests(RegistrationDataTest):
    def test_username_email(self):
        form = RegistrationForm(data=self.valid_data)
        self.assertTrue(form.is_valid())

        data = self.valid_data.copy()
        data[User.USERNAME_FIELD] = data['email']
        form = RegistrationForm(data=data)
        self.assertFalse(form.is_valid())

    def test_username_case(self):
        data = self.valid_data.copy()
        data[User.USERNAME_FIELD] = self.registration_data[User.USERNAME_FIELD].swapcase()
        self.assertTrue(data[User.USERNAME_FIELD] != self.registration_data[User.USERNAME_FIELD])

        form = RegistrationForm(data=data)
        self.assertFalse(form.is_valid())

    def test_disallowed(self):
        with self.settings(DISALLOWED_USERNAMES=('gnome',)):
            data = self.valid_data.copy()
            data[User.USERNAME_FIELD] = "official_GNOME"

            form = RegistrationForm(data=data)
            self.assertFalse(form.is_valid())


class PasswordResetTests(RegistrationDataTest):
    def test_reset_token_pattern(self):
        token = PasswordResetTokenGenerator().make_token(self.registered_user)
        pattern = re.compile(f'^{PASSWORD_RESET_TOKEN_PATTERN}$')

        self.assertTrue(pattern.match(token))


class SettingsTest(TestCase):
    registration_data = [
        {
            User.USERNAME_FIELD: 'bob',
            'email': 'bob@example.com',
            'password': 'mysecretpassword'
        },
        {
            User.USERNAME_FIELD: 'alice',
            'email': 'alice@example.com',
            'password': 'swordfish',
        },
    ]
    registered_users = []

    valid_data = {
        User.USERNAME_FIELD: 'username',
        'email': 'some@example.com',
        'password': 'P@ssw0rd',
    }

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        for data in cls.registration_data:
            cls.registered_users.append(User.objects.create_user(
                username=data[User.USERNAME_FIELD],
                email=data['email'],
                password=data['password']
            ))

    def test_settings(self):
        self.client.force_login(self.registered_users[0])

        response = self.client.post(
            reverse('auth-settings'),
            {
                'profile_form': True,
                'username': self.valid_data[User.USERNAME_FIELD],
                'email': self.registered_users[0].email,
                'display_name': self.registered_users[0].display_name,
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, views.SettingsView.MESSAGE_PROFILE_SAVED)

        response = self.client.post(
            reverse('auth-settings'),
            {
                'profile_form': True,
                'username': getattr(self.registered_users[1], User.USERNAME_FIELD),
                'email': self.registered_users[0].email,
                'display_name': self.registered_users[0].display_name,
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, "profile_form", "username", validators.DUPLICATE_USERNAME)

        response = self.client.post(
            reverse('auth-settings'),
            {
                'profile_form': True,
                'username': self.valid_data[User.USERNAME_FIELD],
                'email': self.registered_users[1].email,
                'display_name': self.registered_users[0].display_name,
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, "profile_form", 'email', validators.DUPLICATE_EMAIL)
