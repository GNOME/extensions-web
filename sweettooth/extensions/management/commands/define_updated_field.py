import os
from django.core.management.base import BaseCommand, CommandError
from sweettooth.extensions.models import ExtensionVersion

class Command(BaseCommand):
    args = ''
    help = 'Replaces updated field of all extensions'

    def handle(self, *args, **options):
        for version in ExtensionVersion.objects.all():
            # We don't have better choise than mtime now
            version.created = os.path.getmtime(version.source.storage.path(version.source.name))

        self.stdout.write('Successfully regenerated all metadata.json files\n')
