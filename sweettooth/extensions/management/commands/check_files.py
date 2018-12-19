
from django.core.management.base import BaseCommand
from sweettooth.extensions.models import ExtensionVersion, STATUS_REJECTED
from zipfile import BadZipfile

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

            except IOError, e:
                self.stderr.write("[%s: %d] Unable to find zip file: %s" % (version.extension.name, version.version, str(e)))
            except BadZipfile, e:
                self.stderr.write("[%s: %d] Bad zip file: %s" % (version.extension.name, version.version, version.source.name))

            if badversion:
                self.stdout.write("[%s: %d] Rejecting" % (version.extension.name, version.version))

            self.stdout.flush()

        self.stdout.write('Done')
