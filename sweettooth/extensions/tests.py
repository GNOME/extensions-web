
import os.path
import json
import tempfile
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile

from django.test import TestCase, TransactionTestCase
from django.core.files.base import File
from django.urls import reverse
from sweettooth.extensions import models, views

from sweettooth.testutils import BasicUserTestCase
from django.test.utils import override_settings

testdata_dir = os.path.join(os.path.dirname(__file__), 'testdata')

def get_test_zipfile(testname):
    original = open(os.path.join(testdata_dir, testname, testname + ".zip"), 'rb')
    new_temp = tempfile.NamedTemporaryFile(suffix=testname + ".zip.temp")
    new_temp.write(original.read())
    new_temp.seek(0)
    original.close()

    return new_temp

class UUIDPolicyTest(TestCase):
    def test_uuid_policy(self):
        self.assertTrue(models.validate_uuid("foo@mecheye.net"))
        self.assertTrue(models.validate_uuid("foo_2@mecheye.net"))
        self.assertTrue(models.validate_uuid("foo-3@mecheye.net"))
        self.assertTrue(models.validate_uuid("Foo4@mecheye.net"))

        for i in range(10):
            self.assertTrue(models.validate_uuid(str(uuid4())))

        self.assertFalse(models.validate_uuid("<Wonderful>"))

        self.assertFalse(models.validate_uuid("foo@gnome.org"))
        self.assertFalse(models.validate_uuid("bar@people.gnome.org"))

        self.assertTrue(models.validate_uuid("bar@i-love-gnome.org"))

class ExtensionPropertiesTest(BasicUserTestCase, TestCase):
    def test_description_parsing(self):
        metadata = {"uuid": "test-metadata@mecheye.net",
                    "name": "Test Metadata",
                    "description": "Simple test metadata"}

        extension = models.Extension.objects.create_from_metadata(metadata, creator=self.user)
        self.assertEqual(extension.first_line_of_description, "Simple test metadata")

        metadata = {"uuid": "test-metadata-2@mecheye.net",
                    "name": "Test Metadata",
                    "description": "First line\nSecond line"}

        extension = models.Extension.objects.create_from_metadata(metadata, creator=self.user)
        self.assertEqual(extension.first_line_of_description, "First line")

        metadata = {"uuid": "test-metadata-3@mecheye.net",
                    "name": "Test Metadata",
                    "description": ""}

        extension = models.Extension.objects.create_from_metadata(metadata, creator=self.user)
        self.assertEqual(extension.first_line_of_description, "")

    def test_shell_versions_json(self):
        metadata = {"uuid": "test-metadata@mecheye.net",
                    "name": "Test Metadata",
                    "shell-version": ["3.2", "3.2.1"]}

        extension = models.Extension.objects.create_from_metadata(metadata, creator=self.user)
        version = models.ExtensionVersion.objects.create(extension=extension,
                                                         status=models.STATUS_UNREVIEWED)
        version.parse_metadata_json(metadata)

        self.assertEqual(version.shell_versions_json, '["3.2", "3.2.1"]')

    def test_session_mode(self):
        metadata = {"uuid": "something1@example.com",
                    "name": "Test Metadata",
                    "shell-version": ["42"],
                    "session-modes": [
                        'forbidden'
                    ]}

        extension = models.Extension.objects.create_from_metadata(metadata, creator=self.user)
        version = models.ExtensionVersion.objects.create(extension=extension,
                                                         status=models.STATUS_UNREVIEWED)
        with self.assertRaises(models.SessionMode.DoesNotExist):
            version.parse_metadata_json(metadata)

        metadata = {"uuid": "something2@example.com",
                    "name": "Test Metadata",
                    "session-modes": [
                        'unlock-dialog'
                    ]}
        extension = models.Extension.objects.create_from_metadata(metadata, creator=self.user)
        version = models.ExtensionVersion.objects.create(extension=extension,
                                                            status=models.STATUS_UNREVIEWED)
        version.parse_metadata_json(metadata)
        version.save()

        self.assertEqual([mode.mode for mode in version.session_modes.all()], ['unlock-dialog'])
        self.assertFalse(extension.uses_session_mode('unlock-dialog'))

        version.status = models.STATUS_ACTIVE
        version.save()
        self.assertTrue(extension.uses_session_mode('unlock-dialog'))

        metadata = {"uuid": "something3@example.com",
                    "name": "Test Metadata",
                    "session-modes": [
                        'gdm',
                        'unlock-dialog'
                    ]}
        extension = models.Extension.objects.create_from_metadata(metadata, creator=self.user)
        version = models.ExtensionVersion.objects.create(extension=extension,
                                                            status=models.STATUS_ACTIVE)
        version.parse_metadata_json(metadata)
        version.save()

        self.assertEqual([mode.mode for mode in version.session_modes.all()], ['gdm', 'unlock-dialog'])
        self.assertTrue(extension.uses_session_mode('gdm'))
        self.assertTrue(extension.uses_session_mode('unlock-dialog'))
        self.assertFalse(extension.uses_session_mode('user'))

class ParseZipfileTest(BasicUserTestCase, TestCase):
    def test_simple_metadata(self):
        metadata = {"uuid": "test-metadata@mecheye.net",
                    "name": "Test Metadata",
                    "description": "Simple test metadata",
                    "url": "http://test-metadata.gnome.org"}

        extension = models.Extension.objects.create_from_metadata(metadata, creator=self.user)
        version = models.ExtensionVersion(extension=extension)
        version.parse_metadata_json(metadata)

        self.assertEqual(extension.name, "Test Metadata")
        self.assertEqual(extension.description, "Simple test metadata")
        self.assertEqual(extension.url, "http://test-metadata.gnome.org")

    def test_simple_zipdata_data(self):
        with get_test_zipfile('SimpleExtension') as f:
            metadata = models.parse_zipfile_metadata(f)

        extension = models.Extension.objects.create_from_metadata(metadata, creator=self.user)
        version = models.ExtensionVersion(extension=extension)
        version.parse_metadata_json(metadata)

        self.assertEqual(extension.uuid, "test-extension@mecheye.net")
        self.assertEqual(extension.name, "Test Extension")
        self.assertEqual(extension.description, "Simple test metadata")
        self.assertEqual(extension.url, "http://test-metadata.gnome.org")

    def test_extra_metadata(self):
        with get_test_zipfile('ExtraMetadata') as f:
            metadata = models.parse_zipfile_metadata(f)

        extension = models.Extension.objects.create_from_metadata(metadata, creator=self.user)
        version = models.ExtensionVersion(extension=extension)
        version.parse_metadata_json(metadata)

        extra = json.loads(version.extra_json_fields)
        self.assertEqual(extension.uuid, "test-extension-2@mecheye.net")
        self.assertEqual(extra["extra"], "This is some good data")
        self.assertTrue("description" not in extra)
        self.assertTrue("url" not in extra)

    def test_bad_zipfile_metadata(self):
        bad_data = BytesIO(b"deadbeef")
        self.assertRaises(models.InvalidExtensionData, models.parse_zipfile_metadata, bad_data)

        with get_test_zipfile('TooLarge') as f:
            with self.assertRaisesMessage(models.InvalidExtensionData, "Zip file is too large"):
                models.parse_zipfile_metadata(f)

        with get_test_zipfile('NoMetadata') as f:
            with self.assertRaisesMessage(models.InvalidExtensionData, "Missing metadata.json"):
                models.parse_zipfile_metadata(f)

        with get_test_zipfile('BadMetadata') as f:
            with self.assertRaisesMessage(models.InvalidExtensionData, "Invalid JSON data"):
                models.parse_zipfile_metadata(f)


class ReplaceMetadataTest(BasicUserTestCase, TestCase):
    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_replace_metadata(self):
        old_zip_file = get_test_zipfile('LotsOfFiles')

        metadata = models.parse_zipfile_metadata(old_zip_file)
        old_zip_file.seek(0)

        extension = models.Extension.objects.create_from_metadata(metadata, creator=self.user)

        version = models.ExtensionVersion.objects.create(extension=extension,
                                          source=File(old_zip_file),
                                          status=models.STATUS_UNREVIEWED)

        version.parse_metadata_json(metadata)
        version.replace_metadata_json()
        version.save()

        new_zip = version.get_zipfile('r')

        old_zip = ZipFile(old_zip_file, 'r')
        self.assertEqual(len(old_zip.infolist()), len(new_zip.infolist()))
        self.assertEqual(new_zip.read("metadata.json").decode('utf-8'),
                         version.make_metadata_json_string())

        for old_info in old_zip.infolist():
            if old_info.filename == "metadata.json":
                continue

            new_info = new_zip.getinfo(old_info.filename)
            self.assertEqual(old_zip.read(old_info), new_zip.read(new_info))
            self.assertEqual(old_info.date_time, new_info.date_time)

        old_zip.close()
        new_zip.close()

class UploadTest(BasicUserTestCase, TransactionTestCase):
    def upload_file(self, zipfile):
        with get_test_zipfile(zipfile) as f:
            return self.client.post(reverse('extensions-upload-file'),
                                    dict(source=f,
                                         gplv2_compliant=True,
                                         tos_compliant=True), follow=True)

    def test_upload_page_works(self):
        response = self.client.get(reverse('extensions-upload-file'))
        self.assertEqual(response.status_code, 200)

    def test_upload_parsing(self):
        response = self.upload_file('SimpleExtension')
        extension = models.Extension.objects.get(uuid="test-extension@mecheye.net")
        version1 = extension.versions.order_by("-version")[0]

        self.assertEqual(version1.status, models.STATUS_UNREVIEWED)
        self.assertEqual(extension.creator, self.user)
        self.assertEqual(extension.name, "Test Extension")
        self.assertEqual(extension.description, "Simple test metadata")
        self.assertEqual(extension.url, "http://test-metadata.gnome.org")

        url = reverse('extensions-detail', kwargs=dict(pk=extension.pk,
                                                       slug=extension.slug))
        self.assertRedirects(response, url)

        version1.status = models.STATUS_ACTIVE
        version1.save()

        # Try again, hoping to get a new version
        self.upload_file('SimpleExtension')

        version2 = extension.versions.order_by("-version")[0]
        self.assertNotEqual(version1, version2)

        # This should be auto-approved.
        self.assertEqual(version2.status, models.STATUS_ACTIVE)
        self.assertEqual(version2.version, version1.version+1)

    def test_upload_large_uuid(self):
        self.upload_file('LargeUUID')

        large_uuid = '1234567890'*9 + '@mecheye.net'
        extension = models.Extension.objects.get(uuid=large_uuid)
        version1 = extension.versions.order_by("-version")[0]

        self.assertEqual(version1.status, models.STATUS_UNREVIEWED)
        self.assertEqual(extension.creator, self.user)
        self.assertEqual(extension.name, "Large UUID test")
        self.assertEqual(extension.description, "Simple test metadata")
        self.assertEqual(extension.url, "http://test-metadata.gnome.org")

    def test_upload_bad_shell_version(self):
        self.upload_file('BadShellVersion')
        extension = models.Extension.objects.get(uuid="bad-shell-version@mecheye.net")
        version1 = extension.versions.order_by("-version")[0]
        self.assertIsNotNone(version1.source)

class ExtensionVersionTest(BasicUserTestCase, TestCase):
    def test_single_version(self):
        metadata = {"name": "Test Metadata",
                    "uuid": "test-1@mecheye.net",
                    "description": "Simple test metadata",
                    "url": "http://test-metadata.gnome.org"}

        extension = models.Extension.objects.create_from_metadata(metadata, creator=self.user)
        version = models.ExtensionVersion.objects.create(extension=extension,
                                                         status=models.STATUS_ACTIVE)
        self.assertEqual(version.version, 1)
        # Make sure that saving again doesn't change the version.
        version.save()
        self.assertEqual(version.version, 1)
        version.save()
        self.assertEqual(version.version, 1)

        self.assertEqual(version.version, 1)
        self.assertEqual(extension.latest_version, version)

    def test_multiple_versions(self):
        metadata = {"name": "Test Metadata 2",
                    "uuid": "test-2@mecheye.net",
                    "description": "Simple test metadata",
                    "url": "http://test-metadata.gnome.org"}

        extension = models.Extension.objects.create_from_metadata(metadata, creator=self.user)

        v1 = models.ExtensionVersion.objects.create(extension=extension,
                                                    status=models.STATUS_ACTIVE)
        self.assertEqual(v1.version, 1)

        v2 = models.ExtensionVersion.objects.create(extension=extension,
                                                    status=models.STATUS_ACTIVE)
        self.assertEqual(v2.version, 2)

        self.assertEqual(list(extension.visible_versions.order_by('version')), [v1, v2])
        self.assertEqual(extension.latest_version, v2)

    def test_unpublished_version(self):
        metadata = {"name": "Test Metadata 3",
                    "uuid": "test-3@mecheye.net",
                    "description": "Simple test metadata",
                    "url": "http://test-metadata.gnome.org"}

        extension = models.Extension.objects.create_from_metadata(metadata, creator=self.user)

        v1 = models.ExtensionVersion.objects.create(extension=extension,
                                                    status=models.STATUS_ACTIVE)
        self.assertEqual(v1.version, 1)

        v2 = models.ExtensionVersion.objects.create(extension=extension,
                                                    status=models.STATUS_UNREVIEWED)
        self.assertEqual(v2.version, 2)

        self.assertEqual(list(extension.visible_versions.order_by('version')), [v1])
        self.assertEqual(extension.latest_version, v1)

        v3 = models.ExtensionVersion.objects.create(extension=extension,
                                                    status=models.STATUS_ACTIVE)
        self.assertEqual(v3.version, 3)

        self.assertEqual(list(extension.visible_versions.order_by('version')), [v1, v3])
        self.assertEqual(extension.latest_version, v3)

    def test_shell_versions_simple(self):
        metadata = {"name": "Test Metadata 4",
                    "uuid": "test-4@mecheye.net",
                    "description": "Simple test metadata",
                    "url": "http://test-metadata.gnome.org",
                    "shell-version": [
                        "3.0.0", "3.0.1", "3.0.2",
                        "40.alpha", "49.beta", "67.rc"
                    ]}

        extension = models.Extension.objects.create_from_metadata(metadata, creator=self.user)
        version = models.ExtensionVersion.objects.create(extension=extension,
                                                         status=models.STATUS_ACTIVE)
        version.parse_metadata_json(metadata)

        shell_versions = sorted(sv.version_string for sv in version.shell_versions.all())
        self.assertEqual(shell_versions, [
            "3.0.0", "3.0.1", "3.0.2",
            "40.alpha", "49.beta", "67.rc"
        ])

    def test_shell_versions_stable(self):
        metadata = {"name": "Test Metadata 5",
                    "uuid": "test-5@mecheye.net",
                    "description": "Simple test metadata",
                    "url": "http://test-metadata.gnome.org",
                    "shell-version": ["3.0", "3.2", "40.0", "56.5"]}

        extension = models.Extension.objects.create_from_metadata(metadata, creator=self.user)

        version = models.ExtensionVersion.objects.create(extension=extension,
                                                         status=models.STATUS_ACTIVE)
        version.parse_metadata_json(metadata)

        shell_versions = sorted(sv.version_string for sv in version.shell_versions.all())
        self.assertEqual(shell_versions, ["3.0", "3.2", "40.0", "56.5"])

class ShellVersionTest(TestCase):
    def test_shell_version_parsing(self):
        lookup_version = models.ShellVersion.objects.lookup_for_version_string
        get_version = models.ShellVersion.objects.get_for_version_string

        # Make sure we don't create a new version
        self.assertEqual(lookup_version("3.0.0"), None)
        version = get_version("3.0.0")
        self.assertEqual(lookup_version("3.0.0"), version)
        self.assertEqual(version.major, 3)
        self.assertEqual(version.minor, 0)
        self.assertEqual(version.point, 0)

        self.assertEqual(lookup_version("3.2"), None)
        version = get_version("3.2")
        self.assertEqual(lookup_version("3.2"), version)
        self.assertEqual(version.major, 3)
        self.assertEqual(version.minor, 2)
        self.assertEqual(version.point, -1)

        self.assertEqual(lookup_version("40"), None)
        version = get_version("40")
        self.assertEqual(lookup_version("40"), version)
        self.assertEqual(version.major, 40)
        self.assertEqual(version.minor, -1)
        self.assertEqual(version.point, -1)

        self.assertEqual(lookup_version("40.alpha"), None)
        version = get_version("40.alpha")
        self.assertEqual(lookup_version("40.alpha"), version)
        self.assertEqual(version.major, 40)
        self.assertEqual(version.minor, -4)
        self.assertEqual(version.point, -1)

        self.assertEqual(lookup_version("51.6"), None)
        version = get_version("51.6")
        self.assertEqual(lookup_version("51.6"), version)
        self.assertEqual(version.major, 51)
        self.assertEqual(version.minor, 6)
        self.assertEqual(version.point, -1)

        self.assertEqual(lookup_version("123.rc"), None)
        version = get_version("123.rc")
        self.assertEqual(lookup_version("123.rc"), version)
        self.assertEqual(version.major, 123)
        self.assertEqual(version.minor, -2)
        self.assertEqual(version.point, -1)

        self.assertEqual(lookup_version("41.3"), None)
        version = get_version("41.3")
        self.assertEqual(lookup_version("41.3"), version)
        self.assertEqual(version.major, 41)
        self.assertEqual(version.minor, 3)
        self.assertEqual(version.point, -1)

        self.assertEqual(lookup_version("42.3.1"), None)
        self.assertEqual(lookup_version("42.3"), None)
        version = get_version("42.3.1")
        self.assertEqual(lookup_version("42.3.1"), version)
        self.assertEqual(lookup_version("42.3"), version)
        self.assertEqual(version.major, 42)
        self.assertEqual(version.minor, 3)
        self.assertEqual(version.point, -1)

        self.assertEqual(lookup_version("51.0.1.2"), None)
        version = get_version("51.0.1.2")
        self.assertEqual(lookup_version("51.0.1.2"), version)
        self.assertEqual(lookup_version("51.0.1"), version)
        self.assertEqual(lookup_version("51.0"), version)
        self.assertEqual(version.major, 51)
        self.assertEqual(version.minor, 0)
        self.assertEqual(version.point, -1)

        version1 = get_version("3.2.2")
        self.assertEqual(lookup_version("3.2.2.1"), version1)

        with self.assertRaises(models.InvalidShellVersion):
            get_version("3.1")

        with self.assertRaises(models.InvalidShellVersion):
            lookup_version("3.1")

        with self.assertRaises(models.InvalidShellVersion):
            lookup_version("3.beta")

    def test_bad_shell_versions(self):
        with self.assertRaises(models.InvalidShellVersion):
            models.parse_version_string("3")

        with self.assertRaises(models.InvalidShellVersion):
            models.parse_version_string("3.2.2.2.1")

        with self.assertRaises(models.InvalidShellVersion):
            models.parse_version_string("a.b")

        with self.assertRaises(models.InvalidShellVersion):
            models.parse_version_string("3.2.a")

        with self.assertRaises(models.InvalidShellVersion):
            models.parse_version_string("40.teta")

class DownloadExtensionTest(BasicUserTestCase, TestCase):
    def download(self, uuid, shell_version):
        url = reverse('extensions-shell-download', kwargs=dict(uuid=uuid))
        return self.client.get(url, dict(shell_version=shell_version), follow=True)

    def test_basic(self):
        zipfile = get_test_zipfile("SimpleExtension")

        metadata = {"name": "Test Metadata 6",
                    "uuid": "test-6@gnome.org",
                    "description": "Simple test metadata",
                    "url": "http://test-metadata.gnome.org"}

        extension = models.Extension.objects.create_from_metadata(metadata, creator=self.user)

        v1 = models.ExtensionVersion.objects.create(extension=extension,
                                                    status=models.STATUS_ACTIVE,
                                                    source=File(zipfile, "version1.zip"))
        v1.parse_metadata_json({"shell-version": ['3.2']})

        v2 = models.ExtensionVersion.objects.create(extension=extension,
                                                    status=models.STATUS_ACTIVE,
                                                    source=File(zipfile, "version1.zip"))
        v2.parse_metadata_json({"shell-version": ['3.4']})

        self.assertRedirects(self.download(metadata['uuid'], '3.2'), v1.source.url)
        self.assertRedirects(self.download(metadata['uuid'], '3.4'), v2.source.url)

    def test_bare_versions(self):
        zipfile = get_test_zipfile("SimpleExtension")

        metadata = {"name": "Test Metadata 7",
                    "uuid": "test-7@gnome.org",
                    "description": "Simple test metadata",
                    "url": "http://test-metadata.gnome.org"}

        extension = models.Extension.objects.create_from_metadata(metadata, creator=self.user)

        v1 = models.ExtensionVersion.objects.create(extension=extension,
                                                    status=models.STATUS_ACTIVE,
                                                    source=File(zipfile, "version1.zip"))
        v1.parse_metadata_json({"shell-version": ['3.2']})

        v2 = models.ExtensionVersion.objects.create(extension=extension,
                                                    status=models.STATUS_ACTIVE,
                                                    source=File(zipfile, "version2.zip"))
        v2.parse_metadata_json({"shell-version": ['3.2.1']})

        self.assertRedirects(self.download(metadata['uuid'], '3.2.0'), v1.source.url)
        self.assertRedirects(self.download(metadata['uuid'], '3.2.1'), v2.source.url)
        self.assertRedirects(self.download(metadata['uuid'], '3.2.2'), v1.source.url)

        v3 = models.ExtensionVersion.objects.create(extension=extension,
                                                    status=models.STATUS_ACTIVE,
                                                    source=File(zipfile, "version3.zip"))
        v3.parse_metadata_json({"shell-version": ['3.2']})

        self.assertRedirects(self.download(metadata['uuid'], '3.2.0'), v3.source.url)
        self.assertRedirects(self.download(metadata['uuid'], '3.2.1'), v3.source.url)
        self.assertRedirects(self.download(metadata['uuid'], '3.2.2'), v3.source.url)

    def test_multiple_versions(self):
        zipfile = get_test_zipfile("SimpleExtension")

        metadata = {"name": "Test Metadata 8",
                    "uuid": "test-8@gnome.org",
                    "description": "Simple test metadata",
                    "url": "http://test-metadata.gnome.org"}

        extension = models.Extension.objects.create_from_metadata(metadata, creator=self.user)

        v1 = models.ExtensionVersion.objects.create(extension=extension,
                                                    status=models.STATUS_ACTIVE,
                                                    source=File(zipfile, "version1.zip"))
        v1.parse_metadata_json({"shell-version": ['3.2.0', '3.2.1', '3.2.2']})

        v2 = models.ExtensionVersion.objects.create(extension=extension,
                                                    status=models.STATUS_ACTIVE,
                                                    source=File(zipfile, "version2.zip"))
        v2.parse_metadata_json({"shell-version": ['3.2.2']})

        self.assertRedirects(self.download(metadata['uuid'], '3.2.0'), v1.source.url)
        self.assertRedirects(self.download(metadata['uuid'], '3.2.1'), v1.source.url)
        self.assertRedirects(self.download(metadata['uuid'], '3.2.2'), v2.source.url)


class UpdateVersionTest(TestCase):
    fixtures = [os.path.join(testdata_dir, 'test_upgrade_data.json')]

    upgrade_uuid = 'upgrade-extension@testcases.sweettooth.mecheye.net'
    reject_uuid = 'reject-extension@testcases.sweettooth.mecheye.net'
    downgrade_uuid = 'downgrade-extension@testcases.sweettooth.mecheye.net'
    nonexistant_uuid = "blah-blah-blah@testcases.sweettooth.mecheye.net"
    full_expected = {
        upgrade_uuid: u'upgrade',
        downgrade_uuid: u'downgrade',
        reject_uuid: u'blacklist'}

    def build_response(self, installed):
        return dict((k, dict(version=v)) for k, v in installed.items())

    def grab_response(self, installed):
        installed = self.build_response(installed)
        response = self.client.get(reverse('extensions-shell-update'),
                                   dict(installed=json.dumps(installed), shell_version='3.2.0'))

        return json.loads(response.content.decode(response.charset))

    def grab_post_response(self, installed):
        installed = self.build_response(installed)
        response = self.client.post(reverse('extensions-shell-update') + "?shell_version=3.2.0",
                                   data=json.dumps(installed),
                                   content_type='application/json')

        return json.loads(response.content.decode(response.charset))

    def test_upgrade_me(self):
        uuid = self.upgrade_uuid

        # The user has an old version, upgrade him
        expected = {uuid: self.full_expected[self.upgrade_uuid]}
        response = self.grab_response({ uuid: 1 })
        self.assertEqual(response, expected)
        response = self.grab_post_response({ uuid: 1 })
        self.assertEqual(response, expected)

        # The user has a newer version on his machine.
        response = self.grab_response({ uuid: 2 })
        self.assertEqual(response, {})
        response = self.grab_post_response({ uuid: 2 })
        self.assertEqual(response, {})

    def test_reject_me(self):
        uuid = self.reject_uuid

        expected = {uuid: self.full_expected[self.reject_uuid]}
        response = self.grab_response({ uuid: 1 })
        self.assertEqual(response, expected)
        response = self.grab_post_response({ uuid: 1 })
        self.assertEqual(response, expected)

        # The user has a newer version than what's on the site.
        response = self.grab_response({ uuid: 2 })
        self.assertEqual(response, {})
        response = self.grab_post_response({ uuid: 2 })
        self.assertEqual(response, {})

    def test_downgrade_me(self):
        uuid = self.downgrade_uuid

        # The user has a rejected version, so downgrade.
        expected = { uuid: self.full_expected[self.downgrade_uuid] }
        response = self.grab_response({ uuid: 2 })
        self.assertEqual(response, expected)
        response = self.grab_post_response({ uuid: 2 })
        self.assertEqual(response, expected)

        # The user has the appropriate version on his machine.
        response = self.grab_response({ uuid: 1 })
        self.assertEqual(response, {})
        response = self.grab_post_response({ uuid: 1 })
        self.assertEqual(response, {})

    def test_nonexistent_uuid(self):
        # The user has an extension that's not on the site.
        response = self.grab_response({ self.nonexistant_uuid: 1 })
        self.assertEqual(response, {})
        response = self.grab_post_response({ self.nonexistant_uuid: 1 })
        self.assertEqual(response, {})

    def test_multiple(self):
        installed = { self.upgrade_uuid: 1,
                      self.reject_uuid: 1,
                      self.downgrade_uuid: 2,
                      self.nonexistant_uuid: 2 }

        response = self.grab_response(installed)
        self.assertEqual(self.full_expected, response)
        response = self.grab_post_response(installed)
        self.assertEqual(self.full_expected, response)

    def test_wrong_version(self):
        uuid = self.upgrade_uuid

        # The user provided wrong version, upgrade him if we have version > 1
        expected = {uuid: self.full_expected[self.upgrade_uuid]}
        response = self.grab_response({uuid: ''})
        self.assertEqual(response, expected)
        response = self.grab_post_response({uuid: ''})
        self.assertEqual(response, expected)

        expected = {uuid: self.full_expected[self.upgrade_uuid]}
        response = self.grab_response({uuid: '0.8.4'})
        self.assertEqual(response, expected)
        response = self.grab_post_response({uuid: '0.8.4'})
        self.assertEqual(response, expected)


class QueryExtensionsTest(BasicUserTestCase, TestCase):
    def get_response(self, params):
        response = self.client.get(reverse('extensions-query'), params)
        return json.loads(response.content.decode(response.charset))

    def gather_uuids(self, params):
        if 'sort' not in params:
            params['sort'] = 'name'

        response = self.get_response(params)
        extensions = response['extensions']
        return [details['uuid'] for details in extensions]

    def create_extension(self, name, **kwargs):
        metadata = dict(uuid=name + "@mecheye.net", name=name)
        return models.Extension.objects.create_from_metadata(metadata,
                                                             creator=self.user,
                                                             **kwargs)

    def test_basic(self):
        one = self.create_extension("one")
        two = self.create_extension("two")

        models.ExtensionVersion.objects.create(extension=one, status=models.STATUS_ACTIVE)
        models.ExtensionVersion.objects.create(extension=two, status=models.STATUS_ACTIVE)

        uuids = self.gather_uuids(dict(uuid=one.uuid))
        self.assertEqual(uuids, [one.uuid])

        uuids = self.gather_uuids(dict(uuid=[one.uuid, two.uuid]))
        self.assertEqual(uuids, [one.uuid, two.uuid])

    def test_basic_visibility(self):
        one = self.create_extension("one")
        two = self.create_extension("two")

        models.ExtensionVersion.objects.create(extension=one, status=models.STATUS_ACTIVE)
        models.ExtensionVersion.objects.create(extension=two, status=models.STATUS_UNREVIEWED)

        # Since two is new, it shouldn't be visible.
        uuids = self.gather_uuids(dict(uuid=[one.uuid, two.uuid]))
        self.assertEqual(uuids, [one.uuid])

        models.ExtensionVersion.objects.create(extension=two, status=models.STATUS_ACTIVE)

        # And now that we have a new version on two, we should have both...
        uuids = self.gather_uuids(dict(uuid=[one.uuid, two.uuid]))
        self.assertEqual(uuids, [one.uuid, two.uuid])

    def test_shell_versions(self):
        one = self.create_extension("one")
        two = self.create_extension("two")

        v = models.ExtensionVersion.objects.create(extension=one, status=models.STATUS_ACTIVE)
        v.parse_metadata_json({"shell-version": ["3.2"]})

        v = models.ExtensionVersion.objects.create(extension=two, status=models.STATUS_ACTIVE)
        v.parse_metadata_json({"shell-version": ["3.3.90"]})

        # Basic querying...
        uuids = self.gather_uuids(dict(shell_version="3.2"))
        self.assertEqual(uuids, [one.uuid])

        uuids = self.gather_uuids(dict(shell_version="3.3.90"))
        self.assertEqual(uuids, [two.uuid])

        # Base version querying.
        uuids = self.gather_uuids(dict(shell_version="3.2.2"))
        self.assertEqual(uuids, [one.uuid])

    def test_complex_visibility(self):
        one = self.create_extension("one")

        v = models.ExtensionVersion.objects.create(extension=one, status=models.STATUS_ACTIVE)
        v.parse_metadata_json({"shell-version": ["3.2"]})

        v = models.ExtensionVersion.objects.create(extension=one, status=models.STATUS_UNREVIEWED)
        v.parse_metadata_json({"shell-version": ["3.3.90"]})

        # Make sure that we don't see one, here - the version that
        # has this shell version is NEW.
        uuids = self.gather_uuids(dict(shell_version="3.3.90"))
        self.assertEqual(uuids, [])

    def test_sort(self):
        one = self.create_extension("one", downloads=50, popularity=15)
        models.ExtensionVersion.objects.create(extension=one, status=models.STATUS_ACTIVE)

        two = self.create_extension("two", downloads=40, popularity=20)
        models.ExtensionVersion.objects.create(extension=two, status=models.STATUS_ACTIVE)

        uuids = self.gather_uuids(dict(sort="name"))
        self.assertEqual(uuids, [one.uuid, two.uuid])
        # name gets asc sort by default
        uuids = self.gather_uuids(dict(sort="name", order="asc"))
        self.assertEqual(uuids, [one.uuid, two.uuid])
        uuids = self.gather_uuids(dict(sort="name", order="desc"))
        self.assertEqual(uuids, [two.uuid, one.uuid])

        uuids = self.gather_uuids(dict(sort="popularity"))
        self.assertEqual(uuids, [two.uuid, one.uuid])
        uuids = self.gather_uuids(dict(sort="popularity", order="desc"))
        self.assertEqual(uuids, [two.uuid, one.uuid])
        uuids = self.gather_uuids(dict(sort="popularity", order="asc"))
        self.assertEqual(uuids, [one.uuid, two.uuid])

        uuids = self.gather_uuids(dict(sort="downloads"))
        self.assertEqual(uuids, [one.uuid, two.uuid])
        uuids = self.gather_uuids(dict(sort="downloads", order="desc"))
        self.assertEqual(uuids, [one.uuid, two.uuid])
        uuids = self.gather_uuids(dict(sort="downloads", order="asc"))
        self.assertEqual(uuids, [two.uuid, one.uuid])

    def test_grab_proper_extension_version(self):
        extension = self.create_extension("extension")

        v = models.ExtensionVersion.objects.create(extension=extension, status=models.STATUS_ACTIVE)
        v.parse_metadata_json({"shell-version": ["3.10", "3.11.1", "3.12"]})

        v = models.ExtensionVersion.objects.create(extension=extension, status=models.STATUS_ACTIVE)
        v.parse_metadata_json({"shell-version": ["3.13.4", "3.14", "3.15.2", "3.16.0", "3.16.1"]})

        v = models.ExtensionVersion.objects.create(extension=extension, status=models.STATUS_ACTIVE)
        v.parse_metadata_json({"shell-version": ["3.16", "3.16.1", "3.17.1", "3.18.2"]})

        v = models.ExtensionVersion.objects.create(extension=extension, status=models.STATUS_ACTIVE)
        v.parse_metadata_json({"shell-version": ["3.20.0"]})

        v = models.ExtensionVersion.objects.create(extension=extension, status=models.STATUS_ACTIVE)
        v.parse_metadata_json({"shell-version": ["3.38.0", "40.alpha", "42.3"]})

        v = models.ExtensionVersion.objects.create(extension=extension, status=models.STATUS_ACTIVE)
        v.parse_metadata_json({"shell-version": ["40"]})

        self.assertEqual(views.grab_proper_extension_version(extension, "3.17.1").version, 3)
        self.assertEqual(views.grab_proper_extension_version(extension, "3.20.0").version, 4)
        self.assertEqual(views.grab_proper_extension_version(extension, "3.2.0"), None)
        self.assertEqual(views.grab_proper_extension_version(extension, "3.4.0"), None)
        self.assertEqual(views.grab_proper_extension_version(extension, "3.20.1"), None)
        self.assertEqual(views.grab_proper_extension_version(extension, "3.4.0", True).version, 1)
        self.assertEqual(views.grab_proper_extension_version(extension, "3.7.4.1", True).version, 1)
        self.assertEqual(views.grab_proper_extension_version(extension, "3.10.0", True).version, 1)
        self.assertEqual(views.grab_proper_extension_version(extension, "3.10.0", False).version, 1)
        self.assertEqual(views.grab_proper_extension_version(extension, "3.11.2", True).version, 1)
        self.assertEqual(views.grab_proper_extension_version(extension, "3.13.4", True).version, 2)
        self.assertEqual(views.grab_proper_extension_version(extension, "3.15.1", True).version, 2)
        self.assertEqual(views.grab_proper_extension_version(extension, "3.15.2", True).version, 2)
        self.assertEqual(views.grab_proper_extension_version(extension, "3.15.3", True).version, 2)
        self.assertEqual(views.grab_proper_extension_version(extension, "3.16", True).version, 3)
        self.assertEqual(views.grab_proper_extension_version(extension, "3.16.1", True).version, 3)
        self.assertEqual(views.grab_proper_extension_version(extension, "3.16.2", True).version, 3)
        self.assertEqual(views.grab_proper_extension_version(extension, "3.17.3", True).version, 3)
        self.assertEqual(views.grab_proper_extension_version(extension, "3.18.3", True).version, 3)
        self.assertEqual(views.grab_proper_extension_version(extension, "3.20.0", True).version, 4)
        self.assertEqual(views.grab_proper_extension_version(extension, "3.24.0", True).version, 4)
        self.assertEqual(views.grab_proper_extension_version(extension, "40.alpha", True).version, 6)
        self.assertEqual(views.grab_proper_extension_version(extension, "40.beta", True).version, 6)
        self.assertEqual(views.grab_proper_extension_version(extension, "40.2", True).version, 6)
        self.assertEqual(views.grab_proper_extension_version(extension, "40.2", False).version, 6)
        self.assertEqual(views.grab_proper_extension_version(extension, "44.2", True).version, 5)
        self.assertEqual(views.grab_proper_extension_version(extension, "129.rc", True).version, 5)
