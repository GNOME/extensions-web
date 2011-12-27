
import os.path
import tempfile
from zipfile import ZipFile

from django.test import TestCase
from django.core.files.base import File
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.utils import simplejson as json
from extensions import models

testdata_dir = os.path.join(os.path.dirname(__file__), 'testdata')

def get_test_zipfile(testname):
    original = open(os.path.join(testdata_dir, testname, testname + ".zip"), 'rb')
    new_temp = tempfile.NamedTemporaryFile(suffix=testname + ".zip.temp")
    new_temp.write(original.read())
    new_temp.seek(0)
    original.close()

    return new_temp

class BasicUserTestCase(object):
    def setUp(self):
        super(BasicUserTestCase, self).setUp()
        self.username = 'TestUser1'
        self.email = 'non-existant@non-existant.tld'
        self.password = 'a random password'
        self.user = User.objects.create_user(self.username, self.email, self.password)

        self.client.login(username=self.username, password=self.password)

class ParseZipfileTest(BasicUserTestCase, TestCase):
    def test_simple_metadata(self):
        metadata = {"name": "Test Metadata",
                    "description": "Simple test metadata",
                    "url": "http://test-metadata.gnome.org"}

        extension = models.Extension(creator=self.user)
        version = models.ExtensionVersion()
        version.extension = extension
        version.parse_metadata_json(metadata)

        self.assertEquals(extension.name, "Test Metadata")
        self.assertEquals(extension.description, "Simple test metadata")
        self.assertEquals(extension.url, "http://test-metadata.gnome.org")

    def test_simple_zipdata_data(self):
        extension = models.Extension(creator=self.user)
        version = models.ExtensionVersion()
        version.extension = extension

        with get_test_zipfile('SimpleExtension') as f:
            metadata = models.parse_zipfile_metadata(f)
        version.parse_metadata_json(metadata)

        self.assertEquals(extension.uuid, "test-extension@mecheye.net")
        self.assertEquals(extension.name, "Test Extension")
        self.assertEquals(extension.description, "Simple test metadata")
        self.assertEquals(extension.url, "http://test-metadata.gnome.org")

    def test_extra_metadata(self):
        extension = models.Extension(creator=self.user)
        version = models.ExtensionVersion()
        version.extension = extension

        with get_test_zipfile('ExtraMetadata') as f:
            metadata = models.parse_zipfile_metadata(f)
        version.parse_metadata_json(metadata)

        extra = json.loads(version.extra_json_fields)
        self.assertEquals(extension.uuid, "test-extension-2@mecheye.net")
        self.assertEquals(extra["extra"], "This is some good data")
        self.assertTrue("description" not in extra)
        self.assertTrue("url" not in extra)

class ReplaceMetadataTest(BasicUserTestCase, TestCase):
    def test_replace_metadata(self):
        extension = models.Extension(creator=self.user)
        version = models.ExtensionVersion()
        version.extension = extension

        old_zip_file = get_test_zipfile('LotsOfFiles')

        metadata = models.parse_zipfile_metadata(old_zip_file)
        old_zip_file.seek(0)

        version.source = File(old_zip_file)

        version.parse_metadata_json(metadata)
        version.replace_metadata_json()
        new_zip = version.get_zipfile('r')

        old_zip = ZipFile(File(old_zip_file), 'r')
        self.assertEqual(len(old_zip.infolist()), len(new_zip.infolist()))
        self.assertEqual(new_zip.read("metadata.json"),
                         version.make_metadata_json_string())

        for old_info in old_zip.infolist():
            if old_info.filename == "metadata.json":
                continue

            new_info = new_zip.getinfo(old_info.filename)
            self.assertEqual(old_zip.read(old_info), new_zip.read(new_info))
            self.assertEqual(old_info.date_time, new_info.date_time)

        old_zip.close()
        new_zip.close()

class UploadTest(BasicUserTestCase, TestCase):
    def upload_file(self, zipfile):
        with get_test_zipfile(zipfile) as f:
            return self.client.post(reverse('extensions-upload-file'),
                                    dict(source=f,
                                         gplv2_compliant=True,
                                         tos_compliant=True), follow=True)

    def test_upload_parsing(self):
        response = self.upload_file('SimpleExtension')
        extension = models.Extension.objects.get(uuid="test-extension@mecheye.net")
        version1 = extension.versions.order_by("-version")[0]

        self.assertEquals(version1.status, models.STATUS_NEW)
        self.assertEquals(extension.creator, self.user)
        self.assertEquals(extension.name, "Test Extension")
        self.assertEquals(extension.description, "Simple test metadata")
        self.assertEquals(extension.url, "http://test-metadata.gnome.org")

        url = reverse('extensions-version-detail', kwargs=dict(pk=version1.pk,
                                                               ext_pk=extension.pk,
                                                               slug=extension.slug))
        self.assertRedirects(response, url)

        version1.status = models.STATUS_ACTIVE
        version1.save()

        # Try again, hoping to get a new version
        self.upload_file('SimpleExtension')

        version2 = extension.versions.order_by("-version")[0]
        self.assertNotEquals(version1, version2)
        self.assertEquals(version2.status, models.STATUS_NEW)
        self.assertEquals(version2.version, version1.version+1)



    def test_upload_large_uuid(self):
        self.upload_file('LargeUUID')

        large_uuid = '1234567890'*9 + '@mecheye.net'
        extension = models.Extension.objects.get(uuid=large_uuid)
        version1 = extension.versions.order_by("-version")[0]

        self.assertEquals(version1.status, models.STATUS_NEW)
        self.assertEquals(extension.creator, self.user)
        self.assertEquals(extension.name, "Large UUID test")
        self.assertEquals(extension.description, "Simple test metadata")
        self.assertEquals(extension.url, "http://test-metadata.gnome.org")


class ExtensionVersionTest(BasicUserTestCase, TestCase):
    def test_single_version(self):
        metadata = {"name": "Test Metadata",
                    "uuid": "test-1@mecheye.net",
                    "description": "Simple test metadata",
                    "url": "http://test-metadata.gnome.org"}

        extension = models.Extension(creator=self.user)
        version = models.ExtensionVersion()
        version.extension = extension
        version.parse_metadata_json(metadata)

        version.status = models.STATUS_ACTIVE
        version.save()

        self.assertEquals(version.version, 1)
        self.assertEquals(extension.latest_version, version)

    def test_multiple_versions(self):
        metadata = {"name": "Test Metadata 2",
                    "uuid": "test-2@mecheye.net",
                    "description": "Simple test metadata",
                    "url": "http://test-metadata.gnome.org"}

        extension = models.Extension(creator=self.user)

        v1 = models.ExtensionVersion()
        v1.extension = extension
        v1.status = models.STATUS_ACTIVE
        v1.parse_metadata_json(metadata)
        v1.save()
        self.assertEquals(v1.version, 1)

        v2 = models.ExtensionVersion()
        v2.extension = extension
        v2.status = models.STATUS_ACTIVE
        v2.parse_metadata_json(metadata)
        v2.save()
        self.assertEquals(v2.version, 2)

        self.assertEquals(list(extension.visible_versions.order_by('version')), [v1, v2])
        self.assertEquals(extension.latest_version, v2)

    def test_unpublished_version(self):
        metadata = {"name": "Test Metadata 3",
                    "uuid": "test-3@mecheye.net",
                    "description": "Simple test metadata",
                    "url": "http://test-metadata.gnome.org"}

        extension = models.Extension(creator=self.user)

        v1 = models.ExtensionVersion()
        v1.extension = extension
        v1.parse_metadata_json(metadata)
        v1.status = models.STATUS_ACTIVE
        v1.save()
        self.assertEquals(v1.version, 1)

        v2 = models.ExtensionVersion()
        v2.extension = extension
        v2.status = models.STATUS_NEW
        v2.parse_metadata_json(metadata)
        v2.save()
        self.assertEquals(v2.version, 2)

        self.assertEquals(list(extension.visible_versions.order_by('version')), [v1])
        self.assertEquals(extension.latest_version, v1)

        v3 = models.ExtensionVersion()
        v3.extension = extension
        v3.status = models.STATUS_ACTIVE
        v3.parse_metadata_json(metadata)
        v3.save()
        self.assertEquals(v3.version, 3)

        self.assertEquals(list(extension.visible_versions.order_by('version')), [v1, v3])
        self.assertEquals(extension.latest_version, v3)

    def test_shell_versions_simple(self):
        metadata = {"name": "Test Metadata 4",
                    "uuid": "test-4@gnome.org",
                    "description": "Simple test metadata",
                    "url": "http://test-metadata.gnome.org",
                    "shell-version": ["3.0.0", "3.0.1", "3.0.2"]}

        extension = models.Extension(creator=self.user)

        version = models.ExtensionVersion()
        version.extension = extension
        version.status = models.STATUS_ACTIVE
        version.parse_metadata_json(metadata)

        version.save()
        shell_versions = sorted(sv.version_string for sv in version.shell_versions.all())
        self.assertEquals(shell_versions, ["3.0.0", "3.0.1", "3.0.2"])

    def test_shell_versions_stable(self):
        metadata = {"name": "Test Metadata 5",
                    "uuid": "test-5@gnome.org",
                    "description": "Simple test metadata",
                    "url": "http://test-metadata.gnome.org",
                    "shell-version": ["3.0", "3.2"]}

        extension = models.Extension(creator=self.user)

        version = models.ExtensionVersion()
        version.extension = extension
        version.status = models.STATUS_ACTIVE
        version.parse_metadata_json(metadata)

        version.save()
        shell_versions = sorted(sv.version_string for sv in version.shell_versions.all())
        self.assertEquals(shell_versions, ["3.0", "3.2"])

class ShellVersionTest(TestCase):
    def test_shell_version_parsing_basic(self):
        get_version = models.ShellVersion.objects.get_for_version_string

        version = get_version("3.0.0")
        self.assertEquals(version.major, 3)
        self.assertEquals(version.minor, 0)
        self.assertEquals(version.point, 0)

        version = get_version("3.2")
        self.assertEquals(version.major, 3)
        self.assertEquals(version.minor, 2)
        self.assertEquals(version.point, -1)

        with self.assertRaises(models.InvalidShellVersion):
            version = get_version("3.1")

class UpdateVersionTest(TestCase):
    fixtures = [os.path.join(testdata_dir, 'test_upgrade_data.json')]

    upgrade_uuid = 'upgrade-extension@testcases.sweettooth.mecheye.net'
    reject_uuid = 'reject-extension@testcases.sweettooth.mecheye.net'
    downgrade_uuid = 'downgrade-extension@testcases.sweettooth.mecheye.net'
    nonexistant_uuid = "blah-blah-blah@testcases.sweettooth.mecheye.net"

    def setUp(self):
        upgrade_pk = models.Extension.objects.get(uuid=self.upgrade_uuid).latest_version.pk
        downgrade_pk = models.Extension.objects.get(uuid=self.downgrade_uuid).latest_version.pk

        self.full_expected = { self.upgrade_uuid: dict(operation='upgrade',
                                                       version=upgrade_pk),
                               self.reject_uuid: dict(operation='blacklist'),
                               self.downgrade_uuid: dict(operation='downgrade',
                                                         version=downgrade_pk) }

    def grab_response(self, installed):
        post_data = dict(installed=json.dumps(installed))

        response = self.client.post(reverse('extensions-shell-update'),
                                    post_data)

        return json.loads(response.content)

    def test_upgrade_me(self):
        uuid = self.upgrade_uuid

        # The user has an old version, upgrade him
        expected = { uuid: self.full_expected[uuid] }
        response = self.grab_response({ uuid: 1 })
        self.assertEqual(response, expected)

        # The user has a newer version on his machine.
        response = self.grab_response({ uuid: 2 })
        self.assertEqual(response, {})

    def test_reject_me(self):
        uuid = self.reject_uuid

        expected = { uuid: self.full_expected[uuid] }
        response = self.grab_response({ uuid: 1 })
        self.assertEqual(response, expected)

        # The user has a newer version than what's on the site.
        response = self.grab_response({ uuid: 2 })
        self.assertEqual(response, {})

    def test_downgrade_me(self):
        uuid = self.downgrade_uuid

        # The user has a rejected version, so downgrade.
        expected = { uuid: self.full_expected[uuid] }
        response = self.grab_response({ uuid: 2 })
        self.assertEqual(response, expected)

        # The user has the appropriate version on his machine.
        response = self.grab_response({ uuid: 1 })
        self.assertEqual(response, {})

    def test_nonexistent_uuid(self):
        # The user has an extension that's not on the site.
        response = self.grab_response({ self.nonexistant_uuid: 1 })
        self.assertEqual(response, {})

    def test_multiple(self):
        installed = { self.upgrade_uuid: 1,
                      self.reject_uuid: 1,
                      self.downgrade_uuid: 2,
                      self.nonexistant_uuid: 2 }

        response = self.grab_response(installed)
        self.assertEqual(self.full_expected, response)

class TestVoteTracker(BasicUserTestCase, TestCase):
    def test_simple(self):
        extension = models.Extension(name="Hi! I'm a talking door!",
                                     creator=self.user,
                                     uuid='talking-door@mecheye.net')
        extension.save()

        response = self.client.post('/ajax/adjust-rating/',
                                    dict(uuid=extension.uuid,
                                         action='like'))

        tracker = models.ExtensionLikeTracker.objects.get(user=self.user,
                                                          extension=extension)
        self.assertEqual(tracker.user, self.user)
        self.assertEqual(tracker.extension, extension)
        self.assertEqual(tracker.vote, True)

        # Man, I love floating point
        extension = models.Extension.objects.get(uuid='talking-door@mecheye.net')
        self.assertTrue(abs(models.confidence(1, 0) - extension.rating) < 0.1)

        response = self.client.post('/ajax/adjust-rating/',
                                    dict(uuid=extension.uuid,
                                         action='dislike'))

        tracker = models.ExtensionLikeTracker.objects.get(user=self.user,
                                                          extension=extension)
        self.assertEqual(tracker.user, self.user)
        self.assertEqual(tracker.extension, extension)
        self.assertEqual(tracker.vote, False)

        extension = models.Extension.objects.get(uuid='talking-door@mecheye.net')
        self.assertTrue(abs(models.confidence(0, 1) - extension.rating) < 0.1)
