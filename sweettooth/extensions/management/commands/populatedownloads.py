from django.core.management.base import BaseCommand

from sweettooth.extensions.models import Extension


class Command(BaseCommand):
    args = "downnload_data [download_data ...]"
    help = (
        "Populates the downloads field from a special whitespace-separated format,"
        " easy to generate with some shell scripts"
    )

    def handle(self, *filenames, **options):
        for filename in filenames:
            with open(filename, "r") as download_data:
                for line in download_data:
                    downloads, uuid = line.split()

                    try:
                        ext = Extension.objects.get(uuid=uuid)
                    except Extension.DoesNotExist:
                        print("Skipping", uuid)
                    else:
                        ext.downloads = int(downloads, 10)
                        ext.save()
