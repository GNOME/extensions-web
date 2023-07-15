import datetime

from django.core.management.base import BaseCommand
from django.db.models import Sum

from sweettooth.extensions.models import Extension


class Command(BaseCommand):
    help = "Update extensions popularity field"

    def handle(self, *args, **options):
        week_ago = datetime.datetime.now() - datetime.timedelta(days=7)

        for extension in Extension.objects.all():
            popularity_data = extension.popularity_items.filter(
                date__gt=week_ago
            ).aggregate(popularity=Sum("offset"))

            popularity_data["popularity"] = popularity_data["popularity"] or 0

            if popularity_data["popularity"] != extension.popularity:
                extension.popularity = popularity_data["popularity"]
                extension.save()

            # TODO: review and restore cleanup
            # ext.popularity_items.filter(date__lte=date).delete()
