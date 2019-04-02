from django_registration import validators

from django.contrib.auth import get_user_model
from django.test.testcases import TestCase
from django.utils.six import text_type
from .forms import AutoFocusRegistrationForm

User = get_user_model()

# registration/tests/test_forms.py
class AuthTests(TestCase):
    valid_data = {
        User.USERNAME_FIELD: 'alice',
        'email': 'alice@example.com',
        'password1': 'swordfish',
        'password2': 'swordfish',
    }

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
