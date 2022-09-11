"""
    GNOME Shell extensions repository
    Copyright (C) 2016-2019  Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""

import re

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIRequestFactory, APITestCase

from rest_registration.api.views import login, register

from .serializers import RegisterUserSerializer

User = get_user_model()


class RegistrationDataTest(APITestCase):
    registration_data = {
        User.USERNAME_FIELD: 'bob',
        'email': 'bob@example.com',
        'password': 'mysecretpassword'
    }
    valid_data = {
        User.USERNAME_FIELD: 'alice',
        'email': 'alice@example.com',
        'password': 'swordfish',
        'password_confirm': 'swordfish',
        'display_name': 'Alice',
    }

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.registered_user = User.objects.create_user(
            username=cls.registration_data[User.USERNAME_FIELD],
            email=cls.registration_data['email'],
            password=cls.registration_data['password']
        )
        cls.factory = APIRequestFactory()


# registration/tests/test_forms.py
class AuthTests(RegistrationDataTest):
    def test_email_uniqueness(self):
        url = reverse('rest_registration:register')

        data = self.valid_data.copy()
        data.update(email=self.registration_data['email'])

        request = self.factory.post(url, data)
        response = register(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data.keys())

    # TODO: make email DB field unique and enable email login
    def test_auth_username_email(self):
        url = reverse('rest_registration:login')

        response = login(self.factory.post(url, {
            'login': self.registration_data[User.USERNAME_FIELD],
            'password': self.registration_data['password']
        }))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = login(self.factory.post(url, {
            'login': self.registration_data['email'],
            'password': self.registration_data['password']
        }))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = login(self.factory.post(url, {
            'login': self.registration_data[User.USERNAME_FIELD],
            'password': self.valid_data['password']
        }))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class RegistrationTests(RegistrationDataTest):
    def test_username_email(self):
        serializer = RegisterUserSerializer(data=self.valid_data.copy())
        self.assertTrue(serializer.is_valid())

        data = self.valid_data.copy()
        data[User.USERNAME_FIELD] = data['email']
        serializer = RegisterUserSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_username_case(self):
        url = reverse('rest_registration:register')

        data = self.valid_data.copy()
        data[User.USERNAME_FIELD] = self.registration_data[User.USERNAME_FIELD].swapcase()
        self.assertTrue(data[User.USERNAME_FIELD] != self.registration_data[User.USERNAME_FIELD])

        request = self.factory.post(url, data)
        response = register(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
