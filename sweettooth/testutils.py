import logging

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APITestCase, APITransactionTestCase

from .auth.authentication import KnoxAuthTokenManager
from .users.models import User


class BasicUserMixin:
    def setUp(self):
        super().setUp()

        self.username = "TestUser1"
        self.email = "non-existant@non-existant.tld"
        self.password = "a random password"
        self.user: User = get_user_model().objects.create_user(
            self.username, self.email, self.password
        )

        self.client.login(username=self.username, password=self.password)


class BasicAPIUserMixin:
    def setUp(self):
        super().setUp()

        manager = KnoxAuthTokenManager()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {manager.provide_token(self.user)['token']}"
        )


class BasicUserTestCase(BasicUserMixin, TestCase):
    pass


class BasicAPIUserTestCase(BasicAPIUserMixin, BasicUserMixin, APITestCase):
    pass


class BasicTransactionUserTestCase(BasicUserMixin, TransactionTestCase):
    pass


class BasicAPITransactionUserTestCase(
    BasicAPIUserMixin, BasicUserMixin, APITransactionTestCase
):
    pass


class SilentDjangoRequestMixin:
    def setUp(self) -> None:
        super().setUp()

        # Reduce the log level to avoid messages like 'bad request'
        logger = logging.getLogger("django.request")
        self.previous_level = logger.getEffectiveLevel()
        logger.setLevel(logging.ERROR)

    def tearDown(self) -> None:
        super().tearDown()

        logger = logging.getLogger("django.request")
        logger.setLevel(self.previous_level)


class SilentDjangoRequestTest(SilentDjangoRequestMixin, TestCase):
    pass
