from django.core.management.base import BaseCommand, CommandError
from sweettooth.extensions.models import ExtensionVersion

class Command(BaseCommand):
    args = ''
    help = 'Regenerates all metadata.json files and replaces them in the zipfile'

    def handle(self, *args, **options):
        versions = ExtensionVersion.objects.all()
        for ver in versions:
            ver.replace_metadata_json()
        self.stdout.write('Successfully regenerated all metadata.json files\n')
