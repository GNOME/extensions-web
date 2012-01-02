
try:
    import json
except ImportError:
    import simplejson as json

import math
import uuid
from zipfile import ZipFile, BadZipfile

from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.db import models
from django.dispatch import Signal

import autoslug
import re
from sorl import thumbnail

(STATUS_NEW, STATUS_LOCKED,
 STATUS_REJECTED, STATUS_INACTIVE,
 STATUS_ACTIVE) = xrange(5)

STATUSES = {
    STATUS_NEW: u"New",
    STATUS_LOCKED: u"Unreviewed",
    STATUS_REJECTED: u"Rejected",
    STATUS_INACTIVE: u"Inactive",
    STATUS_ACTIVE: u"Active",
}

VISIBLE_STATUSES = (STATUS_ACTIVE,)
LIVE_STATUSES = (STATUS_ACTIVE, STATUS_INACTIVE)
REJECTED_STATUSES = (STATUS_REJECTED,)
REVIEWED_STATUSES = (STATUS_REJECTED, STATUS_INACTIVE, STATUS_ACTIVE)

def validate_uuid(uuid):
    if re.match('[-a-zA-Z0-9@._]+$', uuid) is None:
        return False

    if uuid.endswith('.gnome.org'):
        return False

    return True

class ExtensionManager(models.Manager):
    def visible(self):
        return self.filter(versions__status__in=VISIBLE_STATUSES).distinct()

def build_shell_version_map(versions):
    shell_version_map = {}
    for version in versions:
        for shell_version in version.shell_versions.all():
            key = shell_version.version_string
            if key not in shell_version_map:
                shell_version_map[key] = version

            if version.version > shell_version_map[key].version:
                shell_version_map[key] = version

    for key, version in shell_version_map.iteritems():
        shell_version_map[key] = dict(pk = version.pk,
                                      version = version.version)

    return shell_version_map


# Ported to Python, from https://github.com/reddit/reddit/blob/master/r2/r2/lib/db/_sorts.pyx
# Licensed under the CPAL 1.0, written by Reddit, Inc.

def confidence(ups, downs):
    """The confidence sort.
http://www.evanmiller.org/how-not-to-sort-by-average-rating.html"""
    n = ups + downs

    if n == 0:
        return 0

    z = 1.281551565545 # 80% confidence
    p = float(ups) / n

    left = p + 1/(2*n)*z*z
    right = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))
    under = 1+1/n*z*z

    return (left - right) / under


class Extension(models.Model):
    name = models.CharField(max_length=200)
    uuid = models.CharField(max_length=200, unique=True, db_index=True)
    slug = autoslug.AutoSlugField(populate_from="name")
    creator = models.ForeignKey(User, db_index=True)
    description = models.TextField(blank=True)
    url = models.URLField(verify_exists=False, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    downloads = models.PositiveIntegerField(default=0)

    rating = models.FloatField(default=0)

    class Meta:
        permissions = (
            ("can-modify-data", "Can modify extension data"),
        )

    def make_screenshot_filename(self, filename=None):
        return "screenshots/screenshot_%d.png" % (self.pk,)

    screenshot = thumbnail.ImageField(upload_to=make_screenshot_filename, blank=True)

    def make_icon_filename(self, filename=None):
        return "icons/icon_%d.png" % (self.pk,)

    icon = models.ImageField(upload_to=make_icon_filename, blank=True, default="/static/images/plugin.png")

    objects = ExtensionManager()

    def __unicode__(self):
        return self.uuid

    @property
    def visible_versions(self):
        return self.versions.filter(status__in=VISIBLE_STATUSES)

    @property
    def latest_version(self):
        qs = self.visible_versions.order_by("-version")
        if qs.exists():
            return qs[0]
        return None

    def user_can_edit(self, user):
        if user == self.creator:
            return True
        if user.has_perm('extensions.can-modify-data'):
            return True
        return False

    def first_line_of_description(self):
        if not self.description:
            return ""
        return self.description.splitlines()[0]

    def clean(self):
        from django.core.exceptions import ValidationError

        if not validate_uuid(self.uuid):
            raise ValidationError("Invalid UUID")

    def save(self, replace_metadata_json=True, *args, **kwargs):
        super(Extension, self).save(*args, **kwargs)
        if replace_metadata_json:
            for version in self.versions.all():
                if version.source:
                    version.replace_metadata_json()
 
    @property
    def visible_shell_version_map(self):
        return build_shell_version_map(self.visible_versions)

    @property
    def visible_shell_version_map_json(self):
        return json.dumps(self.visible_shell_version_map)

    def get_absolute_url(self):
        return reverse('extensions-detail', kwargs=dict(pk=self.pk,
                                                        slug=self.slug))

    @property
    def likes(self):
        return self.like_trackers.filter(vote=True).count()

    @property
    def dislikes(self):
        return self.like_trackers.filter(vote=False).count()

    def recalculate_rating(self):
        self.rating = confidence(self.likes, self.dislikes)

class ExtensionLikeTracker(models.Model):
    extension = models.ForeignKey(Extension, db_index=True,
                                  related_name='like_trackers')
    user = models.ForeignKey(User, db_index=True)
    vote = models.BooleanField(db_index = True)

    def is_like(self):
        return self.vote

    def is_dislike(self):
        return not self.vote

class ExtensionPopularityItem(models.Model):
    extension = models.ForeignKey(Extension, db_index=True,
                                  related_name='popularity_items')
    offset = models.IntegerField(db_index=True)
    date = models.DateTimeField(auto_now_add=True, db_index=True)

class InvalidShellVersion(Exception):
    pass

class ShellVersionManager(models.Manager):
    def parse_version_string(self, version_string):
        version = version_string.split('.', 2)
        major, minor = version[:2]
        major, minor = int(major), int(minor)

        if len(version) >= 3:
            # 3.0.1, 3.1.4
            point = int(version[2])
        elif len(version) == 2 and minor % 2 == 0:
            # 3.0, 3.2
            point = -1
        else:
            # Two-digit odd versions are illegal: 3.1, 3.3
            raise InvalidShellVersion()

        return major, minor, point

    def lookup_for_version_string(self, version_string):
        major, minor, point = self.parse_version_string(version_string)
        try:
            return self.get(major=major, minor=minor, point=point)
        except self.model.DoesNotExist:
            return None

    def get_for_version_string(self, version_string):
        major, minor, point = self.parse_version_string(version_string)
        obj, created = self.get_or_create(major=major, minor=minor, point=point)
        return obj

class ShellVersion(models.Model):
    major = models.PositiveIntegerField()
    minor = models.PositiveIntegerField()

    # -1 is a flag for the stable release matching
    point = models.IntegerField()

    objects = ShellVersionManager()

    def __unicode__(self):
        return self.version_string

    @property
    def version_string(self):
        if self.point == -1:
            return "%d.%d" % (self.major, self.minor)

        return "%d.%d.%d" % (self.major, self.minor, self.point)

class InvalidExtensionData(Exception):
    pass


def parse_zipfile_metadata(uploaded_file):
    """
    Given a file, extract out the metadata.json, parse, and return it.
    """
    try:
        zipfile = ZipFile(uploaded_file, 'r')
    except BadZipfile:
        raise InvalidExtensionData("Invalid zip file")

    if zipfile.testzip() is not None:
        raise InvalidExtensionData("Invalid zip file")

    total_uncompressed = sum(i.file_size for i in zipfile.infolist())
    if total_uncompressed > 5*1024**3: # 5 MB
        raise InvalidExtensionData("Zip file is too large")

    try:
        metadata = json.load(zipfile.open('metadata.json', 'r'))
    except KeyError:
        # no metadata.json in archive, return nothing
        metadata = {}
    except ValueError:
        # invalid JSON file, raise error
        raise InvalidExtensionData("Invalid JSON data")

    zipfile.close()
    return metadata

# uuid max length + suffix max length
filename_max_length = Extension._meta.get_field('uuid').max_length + len(".v000.shell-version.zip")

class ExtensionVersionManager(models.Manager):
    def locked(self):
        return self.filter(status=STATUS_LOCKED)

    def visible(self):
        return self.filter(status__in=VISIBLE_STATUSES)

class ExtensionVersion(models.Model):
    extension = models.ForeignKey(Extension, related_name="versions")
    version = models.IntegerField(default=0)
    extra_json_fields = models.TextField()
    status = models.PositiveIntegerField(choices=STATUSES.items())
    shell_versions = models.ManyToManyField(ShellVersion)

    class Meta:
        unique_together = ('extension', 'version'),

    def __unicode__(self):
        return "Version %d of %s" % (self.version, self.extension)

    def make_filename(self, filename):
        return "%s.v%d.shell-extension.zip" % (self.extension.uuid, self.version)

    source = models.FileField(upload_to=make_filename,
                              max_length=filename_max_length)

    objects = ExtensionVersionManager()

    @property
    def shell_versions_json(self):
        return json.dumps([sv.version_string for sv in self.shell_versions.all()])

    def make_metadata_json(self):
        """
        Return generated contents of metadata.json
        """
        data = json.loads(self.extra_json_fields)
        fields = dict(
            _generated  = "Generated by SweetTooth, do not edit",
            name        = self.extension.name,
            description = self.extension.description,
            url         = self.extension.url,
            uuid        = self.extension.uuid,
            version     = self.version,
        )

        fields['shell-version'] = [sv.version_string for sv in self.shell_versions.all()]

        data.update(fields)
        return data

    def make_metadata_json_string(self):
        return json.dumps(self.make_metadata_json(), sort_keys=True, indent=2)

    def get_zipfile(self, mode):
        return ZipFile(self.source.storage.path(self.source.name), mode)

    def replace_metadata_json(self):
        """
        In the uploaded extension zipfile, edit metadata.json
        to reflect the new contents.
        """

        # We can't easily *replace* files in a zipfile
        # archive. See http://bugs.python.org/issue6818.
        # Just read all the contents from the old zipfile
        # into memory and then emit a new one with the
        # generated metadata.json
        zipfile_in = self.get_zipfile("r")

        filemap = {}
        for info in zipfile_in.infolist():
            if info.filename == "metadata.json":
                continue

            contents = zipfile_in.read(info)
            filemap[info] = contents

        zipfile = self.get_zipfile("w")
        for info, contents in filemap.iteritems():
            zipfile.writestr(info, contents)

        metadata = self.make_metadata_json()
        zipfile.writestr("metadata.json", self.make_metadata_json_string())
        zipfile.close()

    def parse_metadata_json(self, metadata):
        """
        Given the contents of a metadata.json file, fill in the fields
        of the version and associated extension.
        """
        assert self.extension is not None

        # Only parse the standard data for a new extension
        if self.extension.pk is None:
            self.extension.name = metadata.pop('name', "")
            self.extension.description = metadata.pop('description', "")
            self.extension.url = metadata.pop('url', "")
            self.extension.uuid = metadata.pop('uuid', str(uuid.uuid1()))
            self.extension.save()

            # Due to Django ORM magic and stupidity, this is unfortunately necessary
            self.extension = self.extension

        # FIXME: We shouldn't do this, but Django saving requires it.
        if self.status is None:
            self.status = STATUS_NEW

        self.extra_json_fields = json.dumps(metadata)

        # get version number
        ver_ids = self.extension.versions.order_by('-version')
        try:
            ver_id = ver_ids[0].version + 1
        except IndexError:
            # New extension, no versions yet
            ver_id = 1

        self.version = ver_id

        # ManyToManyField requires a PK, so we need to save.
        self.save()

        for sv_string in metadata.pop('shell-version', []):
            sv = ShellVersion.objects.get_for_version_string(sv_string)
            self.shell_versions.add(sv)

        self.save()

    def get_status_class(self):
        return STATUSES[self.status].lower()

    def is_live(self):
        return self.status in LIVE_STATUSES

    def is_active(self):
        return self.status == STATUS_ACTIVE

    def is_inactive(self):
        return self.status == STATUS_INACTIVE

submitted_for_review = Signal(providing_args=["request", "version"])
reviewed = Signal(providing_args=["request", "version", "review"])
status_changed = Signal(providing_args=["version", "log"])
