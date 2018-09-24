
from django.contrib.auth.models import User

class BasicUserTestCase(object):
    def setUp(self):
        super().setUp()
        self.username = 'TestUser1'
        self.email = 'non-existant@non-existant.tld'
        self.password = 'a random password'
        self.user = User.objects.create_user(self.username, self.email, self.password)

        self.client.login(username=self.username, password=self.password)
