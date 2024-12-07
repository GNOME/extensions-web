from zipfile import BadZipfile
from zlib import error as ZlibError

from django.core.management.base import BaseCommand

from sweettooth.extensions.models import STATUS_ACTIVE, ExtensionVersion


class Command(BaseCommand):
    help = "Checks consistency of extension's archives."

    def _version_message(
        self, version: ExtensionVersion, message: str, error: bool = False
    ):
        channel = self.stdout
        if error:
            channel = self.stderr

        channel.write(
            f"[{version.pk}][{version.extension.name}: {version.version}] {message}"
        )

    def _version_error(self, version: ExtensionVersion, message: str):
        return self._version_message(version, message, True)

    def handle(self, *args, **options):
        for version in ExtensionVersion.objects.all():
            badversion = True
            try:
                with version.get_zipfile("r") as zip:
                    badfile = zip.testzip()

                    if badfile:
                        self._version_error(version, f"Bad entry {badfile} in zip file")
                    else:
                        badversion = False

            except OSError as e:
                self._version_error(version, f"Unable to find zip file: {str(e)}")
            except BadZipfile:
                self._version_error(version, f"Bad zip file: {version.source.name}")
            except ZlibError as e:
                self._version_error(version, f"Zlib error: {str(e)}")

            if badversion:
                if (
                    version.extension.versions.filter(version__gt=version.version)
                    .filter(status=STATUS_ACTIVE)
                    .exists()
                ):
                    self._version_message(version, "Rejecting")
                else:
                    self._version_message(
                        version, "Not rejecting: no newer active versions"
                    )

            self.stdout.flush()

        self.stdout.write("Done")
