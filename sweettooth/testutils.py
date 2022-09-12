import logging

from django.contrib.auth import get_user_model
from django.test import TestCase


class BasicUserTestCase(object):
    def setUp(self):
        super().setUp()

        self.username = "TestUser1"
        self.email = "non-existant@non-existant.tld"
        self.password = "a random password"
        self.user = get_user_model().objects.create_user(
            self.username, self.email, self.password
        )

        self.client.login(username=self.username, password=self.password)


class SilentDjangoRequestTest(TestCase):
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
