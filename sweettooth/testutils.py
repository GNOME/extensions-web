
from django.contrib.auth import get_user_model


class BasicUserTestCase(object):
    def setUp(self):
        super().setUp()

        self.username = 'TestUser1'
        self.email = 'non-existant@non-existant.tld'
        self.password = 'a random password'
        self.user = get_user_model().objects.create_user(self.username, self.email, self.password)

        self.client.login(username=self.username, password=self.password)
