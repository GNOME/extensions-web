# SPDX-License-Identifer: AGPL-3.0-or-later

import json
import os
import re
import tempfile
import zlib
from typing import Any, Literal, Optional
from urllib.parse import quote
from zipfile import BadZipfile, ZipFile

import autoslug
from django.conf import settings
from django.core.files import File
from django.core.files.move import file_move_safe
from django.core.validators import URLValidator
from django.db import models, transaction
from django.dispatch import Signal
from django.forms import ValidationError
from django.urls import reverse
from django.utils.translation import gettext as _

from .fields import HttpURLField

(
    STATUS_UNREVIEWED,
    STATUS_REJECTED,
    STATUS_INACTIVE,
    STATUS_ACTIVE,
    STATUS_WAITING,
) = range(5)

STATUSES = {
    STATUS_UNREVIEWED: "Unreviewed",
    STATUS_REJECTED: "Rejected",
    STATUS_INACTIVE: "Inactive",
    STATUS_ACTIVE: "Active",
    STATUS_WAITING: "Waiting for author",
}


def validate_uuid(uuid):
    if re.match(r"[-a-zA-Z0-9@._]+$", uuid) is None:
        return False

    # Don't blacklist "gnome.org" - we don't want to eliminate
    # world-of-gnome.org or something like that.
    if re.search(r"[.@]gnome\.org$", uuid) is not None:
        return False

    return True


class ExtensionManager(models.Manager):
    def visible(self):
        return self.filter(versions__status=STATUS_ACTIVE).distinct()

    def create_from_metadata(self, metadata, **kwargs):
        instance = self.model(metadata=metadata, **kwargs)
        instance.save()
        return instance


def build_shell_version_map(versions):
    shell_version_map = {}
    for version in versions:
        for shell_version in version.shell_versions.all():
            key = shell_version.version_string
            if key not in shell_version_map:
                shell_version_map[key] = version

            if version.version > shell_version_map[key].version:
                shell_version_map[key] = version

    for key, version in shell_version_map.items():
        shell_version_map[key] = dict(pk=version.pk, version=version.version)

    return shell_version_map


def build_shell_version_array(versions):
    shell_version_map = {}

    for version in versions:
        for shell_version in version.shell_versions.all():
            key = shell_version.version_string
            if key not in shell_version_map:
                shell_version_map[key] = {}

            if version.pk not in shell_version_map[key]:
                shell_version_map[key][version.pk] = dict(
                    pk=version.pk,
                    version=version.display_version,
                )

    return shell_version_map


def make_screenshot_filename(obj, filename=None):
    ext = os.path.splitext(filename)[1].lower()
    return "screenshots/screenshot_%d%s" % (obj.pk, ext)


def make_icon_filename(obj, filename=None):
    ext = os.path.splitext(filename)[1].lower()
    return "icons/icon_%d%s" % (obj.pk, ext)


class SessionMode(models.Model):
    class SessionModes(models.TextChoices):
        USER = "user"
        UNLOCK_DIALOG = "unlock-dialog"
        GDM = "gdm"

    mode = models.CharField(
        primary_key=True,
        max_length=16,
        choices=SessionModes.choices,
    )


class Extension(models.Model):
    class Meta:
        permissions = (("can-modify-data", "Can modify extension data"),)

    MESSAGE_SHELL_VERSION_MISSING = _(
        "You must define `shell-version` key in metadata.json"
    )

    name = models.CharField(max_length=200)
    uuid = models.CharField(max_length=200, unique=True, db_index=True)
    slug = autoslug.AutoSlugField(populate_from="name")
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="extensions",
        db_index=True,
        on_delete=models.PROTECT,
    )
    description = models.TextField(blank=True)
    url = HttpURLField(blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(default=None, blank=True, null=True)
    downloads = models.PositiveIntegerField(default=0)
    popularity = models.IntegerField(default=0)
    recommended = models.BooleanField(default=False)
    rating = models.FloatField(default=0)
    rated = models.IntegerField(default=0)
    allow_comments = models.BooleanField(default=True)
    donation_json_field = None

    screenshot = models.ImageField(upload_to=make_screenshot_filename, blank=True)
    icon = models.ImageField(upload_to=make_icon_filename, blank=True, default="")

    objects = ExtensionManager()

    _http_validator = URLValidator(schemes=("http", "https"))

    def __init__(self, *args, **kwargs):
        metadata = None
        if "metadata" in kwargs:
            metadata = kwargs.pop("metadata")

        super().__init__(*args, **kwargs)

        if metadata:
            self.update_from_metadata(metadata)

    @staticmethod
    def _ensure_list(value: Any | list[str]) -> list[Any]:
        if not isinstance(value, list):
            return [value]

        return value

    def update_from_metadata(self, metadata):
        self.name = metadata.pop("name", "")
        self.description = metadata.pop("description", "")
        self.url = metadata.pop("url", "")
        self.uuid = metadata["uuid"]

        shell_versions = metadata.get("shell-version")
        if not isinstance(shell_versions, list) or not shell_versions:
            raise ValidationError(self.MESSAGE_SHELL_VERSION_MISSING)

        self.donation_json_field: dict[str, str | list[str]] = metadata.get(
            "donations", {}
        )

        supported_types = [item.value for item in DonationUrl.Type]
        for key, values in self.donation_json_field.items():
            if key not in supported_types:
                raise ValidationError(_("Unsupported donation type: %s") % key)

            values = self._ensure_list(values)
            if len(values) > 3:
                raise ValidationError(
                    _('You can not specify more than 3 values for donation type "%s"')
                    % key
                )

            if len(values) < 1:
                raise ValidationError(
                    _('At least one value must be specified for donation type "%s"')
                    % key
                )

            if any(not isinstance(value, str) for value in values):
                raise ValidationError(
                    _(
                        "Value type must be string or list of strings for"
                        ' donation type "%s"'
                    )
                    % key
                )

        # Validate custom URLs
        for url in self._ensure_list(self.donation_json_field.get("custom", [])):
            self._http_validator(url)

    def refresh_donation_urls(self):
        donation_urls = self.donation_urls.all()

        if not self.donation_json_field:
            donation_urls.delete()
            return

        url_ids = []
        for key, values in self.donation_json_field.items():
            values = self._ensure_list(values)
            for url in values:
                donation_url, _ = DonationUrl.objects.get_or_create(
                    extension=self,
                    url_type=key,
                    url=url,
                )
                url_ids.append(donation_url.id)

        self.donation_urls.exclude(id__in=url_ids).delete()

    def clean(self):
        from django.core.exceptions import ValidationError

        if not validate_uuid(self.uuid):
            raise ValidationError("Your extension has an invalid UUID")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.donation_json_field is not None:
            self.refresh_donation_urls()

    def get_absolute_url(self):
        return reverse("extensions-detail", kwargs=dict(pk=self.pk, slug=self.slug))

    def user_can_edit(self, user):
        if user == self.creator:
            return True
        if user.has_perm("extensions.can-modify-data"):
            return True
        return False

    def uses_session_mode(self, mode: str):
        return any(
            session_mode
            for version in self.visible_versions.order_by("-pk")
            for session_mode in version.session_modes.all()
            if session_mode.mode == mode
        )

    def __str__(self):
        return self.uuid

    @property
    def first_line_of_description(self):
        if not self.description:
            return ""
        return self.description.splitlines()[0]

    @property
    def visible_versions(self):
        return self.versions.filter(status=STATUS_ACTIVE)

    @property
    def latest_version(self) -> Optional["ExtensionVersion"]:
        try:
            return self.visible_versions.latest()
        except ExtensionVersion.DoesNotExist:
            return None

    @property
    def visible_shell_version_map(self):
        return build_shell_version_map(self.visible_versions)

    @property
    def visible_shell_version_array(self):
        return build_shell_version_array(self.visible_versions)


class ExtensionPopularityItem(models.Model):
    extension = models.ForeignKey(
        Extension,
        db_index=True,
        on_delete=models.CASCADE,
        related_name="popularity_items",
    )
    offset = models.IntegerField()
    date = models.DateTimeField(auto_now_add=True)


class InvalidShellVersion(Exception):
    pass


def parse_version_string(version_string):
    prerelease_versions = {
        "alpha": -4,
        "beta": -3,
        "rc": -2,
    }
    version = version_string.split(".")
    version_parts = len(version)

    if version_parts < 1 or version_parts > 4:
        raise InvalidShellVersion()

    try:
        major = int(version[0])
        minor = version[1] if version_parts > 1 else -1

        # GNOME 40+
        # https://discourse.gnome.org/t/new-gnome-versioning-scheme/4235
        if major >= 40 and minor in prerelease_versions:
            minor = prerelease_versions.get(minor)
        else:
            minor = int(minor)
    except ValueError:
        raise InvalidShellVersion()

    point = -1
    if version_parts > 2:
        if major < 40:
            # 3.0.1, 3.1.4
            try:
                point = int(version[2])
            except ValueError:
                raise InvalidShellVersion()
    else:
        if major < 40 and (version_parts < 2 or minor % 2 != 0):
            # Two-digit pre-40 odd versions are illegal: 3.1, 3.3
            raise InvalidShellVersion()

    return major, minor, point


class ShellVersionManager(models.Manager):
    def lookup_for_version_string(self, version_string):
        major, minor, point = parse_version_string(version_string)
        try:
            return self.get(major=major, minor=minor, point=point)
        except self.model.DoesNotExist:
            return None

    def get_for_version_string(self, version_string):
        major, minor, point = parse_version_string(version_string)
        try:
            obj = self.get(major=major, minor=minor, point=point)
        except self.model.DoesNotExist:
            obj = self.create(major=major, minor=minor, point=point)

        return obj


class ShellVersion(models.Model):
    major = models.PositiveIntegerField()
    # -3: alpha, -2: beta, -1: rc
    minor = models.IntegerField()

    # -1 is a flag for the stable release matching
    point = models.IntegerField()

    objects = ShellVersionManager()

    def __str__(self):
        return self.version_string

    @property
    def version_string(self):
        prerelease_versions = {-4: "alpha", -3: "beta", -2: "rc"}

        # GNOME 40+: unstable versions
        # https://discourse.gnome.org/t/new-gnome-versioning-scheme/4235
        if self.major >= 40:
            if self.minor < -1:
                return "%d.%s" % (
                    self.major,
                    prerelease_versions.get(self.minor, "unknown"),
                )
            elif self.minor == -1:
                return "%d" % (self.major)

        if self.point == -1:
            return "%d.%d" % (self.major, self.minor)

        return "%d.%d.%d" % (self.major, self.minor, self.point)


class InvalidExtensionData(Exception):
    def __init__(self, message: str, *args: object) -> None:
        super().__init__(message, *args)
        self.message = message


def parse_zipfile_metadata(uploaded_file):
    """
    Given a file, extract out the metadata.json, parse, and return it.
    """
    try:
        with ZipFile(uploaded_file, "r") as zipfile:
            if zipfile.testzip() is not None:
                raise InvalidExtensionData("Invalid zip file")

            total_uncompressed = sum(i.file_size for i in zipfile.infolist())
            if total_uncompressed > 5 * 1024 * 1024:  # 5 MB
                raise InvalidExtensionData("Zip file is too large")

            try:
                info = zipfile.getinfo("extension.js")
                if info.file_size < 1:
                    raise InvalidExtensionData("The extension.js file is empty")
            except KeyError as ex:
                raise InvalidExtensionData("Missing extension.js") from ex

            try:
                with zipfile.open("metadata.json", "r") as metadata_fp:
                    return json.load(metadata_fp)
            except KeyError as ex:
                # no metadata.json in archive, raise error
                raise InvalidExtensionData("Missing metadata.json") from ex
            except ValueError as ex:
                # invalid JSON file, raise error
                raise InvalidExtensionData("Invalid JSON data") from ex

    except (BadZipfile, zlib.error) as ex:
        raise InvalidExtensionData("Invalid zip file") from ex


# uuid max length + suffix max length
filename_max_length = Extension._meta.get_field("uuid").max_length + len(
    ".v000.shell-version.zip"
)


class ExtensionVersionManager(models.Manager):
    def unreviewed(self):
        return self.filter(status=STATUS_UNREVIEWED)

    def waiting(self):
        return self.filter(status=STATUS_WAITING)

    def visible(self):
        return self.filter(status=STATUS_ACTIVE)


def make_filename(obj, filename=None):
    return "%s.v%d.shell-extension.zip" % (obj.extension.uuid, obj.version)


def version_name_validator(value):
    stripped_value = value.strip(".")
    if not stripped_value:
        raise ValidationError(_("Version name cannot be just spaces or dots."))

    pattern = r"^[a-zA-Z0-9 .]*$"
    if not re.match(pattern, stripped_value):
        raise ValidationError(
            _(
                "Only alphanumeric characters (eng), spaces, and dots are"
                " allowed for version name."
            )
        )


class ExtensionVersion(models.Model):
    class Meta:
        unique_together = (("extension", "version"),)
        get_latest_by = "version"

        indexes = (
            models.Index(
                fields=("extension", "status"), name="extension_id__status_idx"
            ),
        )

    extension: Extension = models.ForeignKey(
        Extension, on_delete=models.CASCADE, related_name="versions"
    )
    version: int = models.IntegerField(default=0)
    version_name = models.CharField(
        default=None,
        blank=True,
        null=True,
        validators=[version_name_validator],
        max_length=16,
    )
    extra_json_fields = models.TextField()
    status = models.PositiveIntegerField(choices=STATUSES.items())
    shell_versions = models.ManyToManyField(ShellVersion)
    session_modes = models.ManyToManyField(SessionMode)
    created = models.DateTimeField(auto_now_add=True, null=True)

    source = models.FileField(upload_to=make_filename, max_length=filename_max_length)

    objects = ExtensionVersionManager()

    _extra_json_field_position = None

    def __init__(self, *args, **kwargs):
        if "metadata" in kwargs:
            self.metadata = kwargs.pop("metadata").copy()
        else:
            self.metadata = {}

        extra_metadata = self.metadata.copy()
        for known_field in ("shell-versions", "session-modes"):
            if known_field in extra_metadata:
                del extra_metadata[known_field]

        if len(args) < self._get_extra_json_field_position():
            kwargs["extra_json_fields"] = json.dumps(extra_metadata)

        super().__init__(*args, **kwargs)

    def _get_extra_json_field_position(self):
        if self._extra_json_field_position is not None:
            return self._extra_json_field_position

        self._extra_json_field_position = next(
            (
                index
                for index, field in enumerate(
                    [f for f in self._meta.get_fields() if getattr(f, "attname", None)]
                )
                if field.attname == "extra_json_fields"
            )
        )

        return self._extra_json_field_position

    @property
    def shell_versions_json(self):
        return json.dumps([sv.version_string for sv in self.shell_versions.all()])

    @property
    def display_version(self) -> str:
        if self.version_name:
            return self.version_name

        return str(self.version)

    @property
    def display_full_version(self) -> str:
        if self.version_name:
            return f"{self.version_name} ({self.version})"

        return str(self.version)

    def make_metadata_json(self):
        """
        Return generated contents of metadata.json
        """
        data = json.loads(self.extra_json_fields)
        fields = dict(
            _generated="Generated by SweetTooth, do not edit",
            name=self.extension.name,
            description=self.extension.description,
            url=self.extension.url,
            uuid=self.extension.uuid,
            version=self.version,
        )

        fields["session-modes"] = [m.mode for m in self.session_modes.all()]
        if not fields["session-modes"]:
            del fields["session-modes"]

        fields["shell-version"] = [
            sv.version_string for sv in self.shell_versions.all()
        ]

        if self.version_name:
            fields["version-name"] = self.version_name

        data.update(fields)
        return data

    def make_metadata_json_string(self):
        return json.dumps(self.make_metadata_json(), sort_keys=True, indent=2)

    def get_zipfile(self, mode: Literal["r", "w", "x", "a"]) -> ZipFile:
        return ZipFile(self.source.file, mode)

    def _replace_metadata_json(self):
        """
        In the uploaded extension zipfile, edit metadata.json
        to reflect the new contents.
        """

        # We can't easily *replace* files in a zipfile
        # archive. See https://bugs.python.org/issue6818.
        # Just read all the contents from the old zipfile
        # into memory and then emit a new one with the
        # generated metadata.json
        with tempfile.NamedTemporaryFile("w+b", delete=False) as temp_file:
            with (
                self.get_zipfile("r") as zipfile_in,
                ZipFile(temp_file.file, "w") as zipfile,
            ):
                for info in zipfile_in.infolist():
                    if info.filename == "metadata.json":
                        continue

                    zipfile.writestr(info, zipfile_in.read(info))

                zipfile.writestr("metadata.json", self.make_metadata_json_string())

            temp_file.flush()
            temp_file.seek(0)

            file_move_safe(self.source.path, f"{self.source.path}-replace")
            self.source.storage.save(self.source.name, File(temp_file.file))
            try:
                os.remove(f"{self.source.path}-replace")
                self.source.file.close()
                self.source.file = None
            except Exception:
                pass

    @transaction.atomic
    def save(self, *args, **kwargs):
        assert self.extension is not None

        if self.version == 0:
            # Get version number
            try:
                # Don't use extension.latest_version, as that will
                # give us the latest visible version.
                self.version = self.extension.versions.latest().version + 1
            except self.DoesNotExist:
                self.version = 1

        adding = self._state.adding

        super().save(*args, **kwargs)

        kwargs.pop("force_insert", None)

        for sv_string in self.metadata.pop("shell-version", []):
            try:
                self.shell_versions.add(
                    ShellVersion.objects.get_for_version_string(sv_string)
                )
            except InvalidShellVersion:
                # For now, ignore invalid shell versions, rather than
                # causing a fit.
                continue

        if "session-modes" in self.metadata:
            self.session_modes.set(
                [
                    SessionMode.objects.get(mode=mode)
                    for mode in self.metadata.pop("session-modes", [])
                ]
            )

        super().save(*args, **kwargs)

        if adding and self.source:
            self._replace_metadata_json()

    def get_absolute_url(self):
        return self.extension.get_absolute_url()

    def get_status_class(self):
        return STATUSES[self.status].lower()

    def is_approved(self):
        return self.status in (STATUS_ACTIVE, STATUS_INACTIVE)

    def is_active(self):
        return self.status == STATUS_ACTIVE

    def is_inactive(self):
        return self.status == STATUS_INACTIVE

    def __str__(self):
        return "Version %s of %s" % (
            self.display_full_version,
            self.extension,
        )


class DonationUrl(models.Model):
    class Type(models.TextChoices):
        BUY_ME_A_COFFEE = "buymeacoffee", "Buy Me a Coffee"
        CUSTOM = "custom", "Link"
        GITHUB = "github", "GitHub"
        KO_FI = "kofi", "Ko-fi"
        LIBERAPAY = "liberapay", "Liberapay"
        OPENCOLLECTIVE = "opencollective", "Open Collective"
        PATREON = "patreon", "Patreon"
        PAYPAL = "paypal", "PayPal"

    class Meta:
        indexes = (
            models.Index(
                fields=("extension", "url_type"), name="extension_id__url_type_idx"
            ),
        )

    TYPE_BASE_URLS = {
        Type.BUY_ME_A_COFFEE: "https://www.buymeacoffee.com",
        Type.GITHUB: "https://github.com/sponsors",
        Type.KO_FI: "https://ko-fi.com",
        Type.LIBERAPAY: "https://liberapay.com",
        Type.OPENCOLLECTIVE: "https://opencollective.com",
        Type.PATREON: "https://www.patreon.com",
        Type.PAYPAL: "https://paypal.me",
    }

    extension: Extension = models.ForeignKey(
        Extension, on_delete=models.CASCADE, related_name="donation_urls"
    )
    url_type = models.CharField(
        max_length=32, choices=Type.choices, default=Type.CUSTOM
    )
    url = models.CharField(max_length=256)

    @property
    def full_url(self):
        if self.url_type in self.TYPE_BASE_URLS:
            return f"{self.TYPE_BASE_URLS[self.url_type]}/{quote(self.url, safe='')}"

        return self.url

    def __str__(self) -> str:
        return f"[{self.extension}] {self.url_type} ({self.url})"


# providing_args=["request", "version"]
submitted_for_review = Signal()
# providing_args=["request", "version", "review"]
reviewed = Signal()
