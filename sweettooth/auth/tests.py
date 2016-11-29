from registration import validators
from registration.tests.base import RegistrationTestCase

from forms import AutoFocusRegistrationForm
from django.contrib.auth import get_user_model
from django.utils.six import text_type

User = get_user_model()

# registration/tests/test_forms.py
class AuthTests(RegistrationTestCase):
    def test_email_uniqueness(self):
        User.objects.create(
            username='bob',
            email=self.valid_data['email'],
            password=self.valid_data['password1']
        )

        form = AutoFocusRegistrationForm(
            data=self.valid_data.copy()
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors['email'],
            [text_type(validators.DUPLICATE_EMAIL)]
        )

        data = self.valid_data.copy()
        data.update(email='bob@example.com')
        form = AutoFocusRegistrationForm(
            data=data
        )
        self.assertTrue(form.is_valid())
