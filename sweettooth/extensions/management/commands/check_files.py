from django.core.management.base import BaseCommand
from sweettooth.extensions.models import ExtensionVersion, STATUS_ACTIVE, STATUS_REJECTED
from zipfile import BadZipfile
from zlib import error as ZlibError
import codecs

class Command(BaseCommand):
    help = "Checks consistency of extension's archives."
    logs_directory = None

    def add_arguments(self, parser):
        parser.add_argument('logs_directory', nargs='?', help="Directory to write logs.")


    def handle(self, *args, **options):
        if 'logs_directory' in options:
            self.logs_directory = options['logs_directory']

        for version in ExtensionVersion.objects.exclude(status=STATUS_REJECTED):
            badversion = True
            try:
                with version.get_zipfile('r') as zip:
                    badfile = zip.testzip()

                    if badfile:
                        self.error("[%s: %d] Bad entry %s in zip file" % (version.extension.name, version.version, badfile))
                    else:
                        badversion = False

            except IOError, e:
                self.error("[%s: %d] Unable to find zip file: %s" % (version.extension.name, version.version, str(e)))
            except BadZipfile, e:
                self.error("[%s: %d] Bad zip file: %s" % (version.extension.name, version.version, version.source.name))
            except ZlibError, e:
                self.error("[%s: %d] Zlib error: %s" % (version.extension.name, version.version, str(e)))

            if badversion:
                if version.extension.versions.filter(version__gt=version.version).filter(status=STATUS_ACTIVE).exists():
                    self.message("[%s: %d] Rejecting" % (version.extension.name, version.version))
                else:
                    self.message("[%s: %d] Not rejecting: no newer active versions" % (version.extension.name, version.version))

            self.stdout.flush()

        self.message('Done')


    def message(self, string):
        self.stdout.write(string)

        if self.logs_directory:
            with codecs.open("%s/check_files_out" % self.logs_directory, 'a', encoding='utf-8') as file:
                file.write("%s\n" % string)

    def error(self, string):
        self.stderr.write(string)

        if self.logs_directory:
            with codecs.open("%s/check_files_err" % self.logs_directory, 'a', encoding='utf-8') as file:
                file.write("%s\n" % string)
