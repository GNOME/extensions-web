"""
    GNOME Shell Extensions Repository
    Copyright (C) 2013 Jasper St. Pierre <jstpierre@mecheye.net>
    Copyright (C) 2022 Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""

from zipfile import BadZipFile

from django.core.files.base import ContentFile, File
from django.test import TestCase

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
