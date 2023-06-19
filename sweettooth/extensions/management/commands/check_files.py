from django.core.management.base import BaseCommand
from sweettooth.extensions.models import ExtensionVersion, STATUS_ACTIVE, STATUS_REJECTED
from zipfile import BadZipfile
from zlib import error as ZlibError


class Command(BaseCommand):
    help = "Checks consistency of extension's archives."

    def handle(self, *args, **options):
        for version in ExtensionVersion.objects.exclude(status=STATUS_REJECTED):
            badversion = True
            try:
                with version.get_zipfile('r') as zip:
                    badfile = zip.testzip()

                    if badfile:
                        self.stderr.write("[%s: %d] Bad entry %s in zip file" % (version.extension.name, version.version, badfile))
                    else:
                        badversion = False

            except IOError as e:
                self.stderr.write("[%s: %d] Unable to find zip file: %s" % (version.extension.name, version.version, str(e)))
            except BadZipfile:
                self.stderr.write("[%s: %d] Bad zip file: %s" % (version.extension.name, version.version, version.source.name))
            except ZlibError as e:
                self.stderr.write("[%s: %d] Zlib error: %s" % (version.extension.name, version.version, str(e)))

            if badversion:
                if version.extension.versions.filter(version__gt=version.version).filter(status=STATUS_ACTIVE).exists():
                    self.stdout.write("[%s: %d] Rejecting" % (version.extension.name, version.version))
                else:
                    self.stdout.write("[%s: %d] Not rejecting: no newer active versions" % (version.extension.name, version.version))

            self.stdout.flush()

        self.stdout.write('Done')
