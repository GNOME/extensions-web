
from django.core.management.base import BaseCommand
from sweettooth.extensions.models import Extension
from sweettooth.extensions.search import index_extension

class Command(BaseCommand):
    args = ''
    help = 'Regenerates all metadata.json files and replaces them in the zipfile'

    def handle(self, *args, **options):
        count = Extension.objects.count()
        message_length = 0
        for i, ext in enumerate(Extension.objects.all()):
            index_extension(ext)
            message = ("Indexed (%d / %d) %s" % (i + 1, count, ext.uuid))
            message_length = max(message_length, len(message))
            self.stdout.write(message.ljust(message_length) + "\r")
            self.stdout.flush()
        self.stdout.write('\nSuccessfully indexed all extensions\n')
