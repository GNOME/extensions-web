"""
    GNOME Shell extensions repository
    Copyright (C) 2016-2019  Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""

from django_registration import validators

from django.contrib.auth import get_user_model
from django.test.testcases import TestCase
from django.utils.six import text_type
from .forms import AutoFocusRegistrationForm

User = get_user_model()

# registration/tests/test_forms.py
class AuthTests(TestCase):
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
    def setUp(cls):
        User.objects.create_user(
            username=cls.registration_data[User.USERNAME_FIELD],
            email=cls.registration_data['email'],
            password=cls.registration_data['password']
        )

    def test_email_uniqueness(self):
        data = self.valid_data.copy()
        data.update(email = self.registration_data['email'])
        form = AutoFocusRegistrationForm(
            data=data
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors['email'],
            [text_type(validators.DUPLICATE_EMAIL)]
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
