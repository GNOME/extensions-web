from django.contrib.auth import get_user_model

from rest_framework.test import APITestCase

from knox.models import AuthToken


class BasicUserTestCase(APITestCase):
    def setUp(self):
        super().setUp()

        self.username = 'TestUser1'
        self.email = 'non-existant@non-existant.tld'
        self.password = 'a random password'
        self.user = get_user_model().objects.create_user(self.username, self.email, self.password)

        _, token = AuthToken.objects.create(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
