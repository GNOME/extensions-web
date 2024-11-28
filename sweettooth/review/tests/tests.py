# SPDX-License-Identifer: AGPL-3.0-or-later

from zipfile import BadZipFile

from django.core.files.base import ContentFile, File
from django.test import RequestFactory, TestCase

from sweettooth.extensions import models
from sweettooth.extensions.tests import get_test_zipfile
from sweettooth.review.views import (
    get_old_version,
    should_auto_approve,
    should_auto_approve_changeset,
)
from sweettooth.testutils import BasicUserTestCase


class DiffViewTest(BasicUserTestCase, TestCase):
    def test_get_zipfiles(self):
        metadata = {
            "uuid": "test-metadata@mecheye.net",
            "name": "Test Metadata",
            "shell-version": ["44"],
        }

        extension = models.Extension.objects.create_from_metadata(
            metadata, creator=self.user
        )
        with self.assertRaises(BadZipFile):
            models.ExtensionVersion.objects.create(
                extension=extension,
                source=File(ContentFile("doot doo"), name="aa"),
                status=models.STATUS_UNREVIEWED,
            )

        # This one is broken...
        version2 = models.ExtensionVersion.objects.create(
            extension=extension, source="", status=models.STATUS_UNREVIEWED
        )
        self.assertEqual(None, get_old_version(version2))

        with self.assertRaises(BadZipFile):
            models.ExtensionVersion.objects.create(
                extension=extension,
                source=File(ContentFile("doot doo"), name="bb"),
                status=models.STATUS_UNREVIEWED,
            )


class TestAutoApproveLogic(BasicUserTestCase, TestCase):
    def build_changeset(self, added=None, deleted=None, changed=None, unchanged=None):
        return dict(
            added=added or [],
            deleted=deleted or [],
            changed=changed or [],
            unchanged=unchanged or [],
        )

    def test_auto_approve_logic(self):
        self.assertTrue(should_auto_approve_changeset(self.build_changeset()))
        self.assertTrue(
            should_auto_approve_changeset(
                self.build_changeset(changed=["metadata.json"])
            )
        )
        self.assertTrue(
            should_auto_approve_changeset(
                self.build_changeset(
                    changed=[
                        "metadata.json",
                        "po/en_GB.po",
                        "images/new_fedora.png",
                        "stylesheet.css",
                    ]
                )
            )
        )
        self.assertTrue(
            should_auto_approve_changeset(
                self.build_changeset(changed=["stylesheet.css"], added=["po/zn_CH.po"])
            )
        )

        self.assertFalse(
            should_auto_approve_changeset(
                self.build_changeset(changed=["extension.js"])
            )
        )
        self.assertFalse(
            should_auto_approve_changeset(
                self.build_changeset(changed=["secret_keys.json"])
            )
        )
        self.assertFalse(
            should_auto_approve_changeset(
                self.build_changeset(changed=["libbignumber/BigInteger.js"])
            )
        )
        self.assertFalse(
            should_auto_approve_changeset(
                self.build_changeset(added=["libbignumber/BigInteger.js"])
            )
        )

    def test_auto_approve_metadata(self):
        metadata = {
            "uuid": "something1@example.com",
            "name": "Test Metadata",
            "shell-version": ["42"],
        }
        zipfile = get_test_zipfile("SimpleExtension")

        extension: models.Extension = models.Extension.objects.create_from_metadata(
            metadata, creator=self.user
        )
        version = models.ExtensionVersion.objects.create(
            extension=extension,
            metadata=metadata,
            source=File(zipfile, "version1.zip"),
            status=models.STATUS_ACTIVE,
        )

        version: models.ExtensionVersion = models.ExtensionVersion.objects.create(
            extension=extension,
            metadata=metadata | {"session-modes": ["user"]},
            source=File(zipfile, "version2.zip"),
            status=models.STATUS_UNREVIEWED,
        )
        self.assertFalse(should_auto_approve(version))

        version: models.ExtensionVersion = models.ExtensionVersion.objects.create(
            extension=extension,
            metadata=metadata | {"shell-version": ["43"]},
            source=File(zipfile, "version3.zip"),
            status=models.STATUS_UNREVIEWED,
        )
        self.assertTrue(should_auto_approve(version))

        version: models.ExtensionVersion = models.ExtensionVersion.objects.create(
            extension=extension,
            metadata=metadata | {"shell-version": ["45"]},
            source=File(zipfile, "version4.zip"),
            status=models.STATUS_UNREVIEWED,
        )
        self.assertFalse(should_auto_approve(version))

        version: models.ExtensionVersion = models.ExtensionVersion.objects.create(
            extension=extension,
            metadata=metadata | {"shell-version": ["42", "64"]},
            source=File(zipfile, "version5.zip"),
            status=models.STATUS_UNREVIEWED,
        )
        self.assertFalse(should_auto_approve(version))


class TestAutoRejectLogic(BasicUserTestCase, TestCase):
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()

    @staticmethod
    def refresh_from_db(*args: models.ExtensionVersion):
        for version in args:
            version.refresh_from_db()

    def test_auto_reject(self):
        metadata = {
            "uuid": "something1@example.com",
            "name": "Test Metadata",
            "shell-version": ["42"],
        }
        zipfile = get_test_zipfile("SimpleExtension")

        extension: models.Extension = models.Extension.objects.create_from_metadata(
            metadata, creator=self.user
        )
        version1 = models.ExtensionVersion.objects.create(
            extension=extension,
            metadata=metadata,
            source=File(zipfile, "version1.zip"),
            status=models.STATUS_UNREVIEWED,
        )

        request = self.factory.post("/upload")
        request.user = self.user

        models.submitted_for_review.send(
            sender=request, request=request, version=version1
        )

        self.refresh_from_db(version1)

        self.assertEqual(version1.status, models.STATUS_UNREVIEWED)

        version2: models.ExtensionVersion = models.ExtensionVersion.objects.create(
            extension=extension,
            metadata=metadata | {"shell-version": ["42", "43"]},
            source=File(zipfile, "version2.zip"),
            status=models.STATUS_UNREVIEWED,
        )

        models.submitted_for_review.send(
            sender=request, request=request, version=version2
        )

        self.refresh_from_db(version1, version2)

        self.assertEqual(version1.status, models.STATUS_UNREVIEWED)
        self.assertEqual(version2.status, models.STATUS_UNREVIEWED)

        version3: models.ExtensionVersion = models.ExtensionVersion.objects.create(
            extension=extension,
            metadata=metadata,
            source=File(zipfile, "version3.zip"),
            status=models.STATUS_UNREVIEWED,
        )

        models.submitted_for_review.send(
            sender=request, request=request, version=version3
        )

        self.refresh_from_db(version1, version2, version3)

        self.assertEqual(version1.status, models.STATUS_REJECTED)
        self.assertEqual(version2.status, models.STATUS_UNREVIEWED)
        self.assertEqual(version3.status, models.STATUS_UNREVIEWED)

        version4: models.ExtensionVersion = models.ExtensionVersion.objects.create(
            extension=extension,
            metadata=metadata,
            source=File(zipfile, "version4.zip"),
            status=models.STATUS_UNREVIEWED,
        )

        models.submitted_for_review.send(
            sender=request, request=request, version=version4
        )

        self.refresh_from_db(version1, version2, version3, version4)

        self.assertEqual(version1.status, models.STATUS_REJECTED)
        self.assertEqual(version2.status, models.STATUS_UNREVIEWED)
        self.assertEqual(version3.status, models.STATUS_REJECTED)
        self.assertEqual(version4.status, models.STATUS_UNREVIEWED)
