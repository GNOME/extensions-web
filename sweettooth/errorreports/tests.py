
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from sweettooth.extensions.models import Extension, ExtensionVersion, STATUS_ACTIVE
from sweettooth.errorreports import models, views

from sweettooth.testutils import BasicUserTestCase

class SubmitErrorReportTestCase(BasicUserTestCase, TestCase):
    def test_email_sent(self):
        metadata = {"uuid": "test-metadata@mecheye.net",
                    "name": "Test Metadata",
                    "description": "Simple test metadata",
                    "url": "http://test-metadata.gnome.org"}

        extension = Extension.objects.create_from_metadata(metadata, creator=self.user)
        ExtensionVersion.objects.create(extension=extension, metadata=metadata, status=STATUS_ACTIVE)

        comment = "YOUR EXTENSION SUCKS IT BROKE"

        self.client.post(reverse(views.report_error,
                                 kwargs=dict(pk=extension.pk)),
                         dict(comment=comment), follow=True)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(comment, mail.outbox[0].body)
