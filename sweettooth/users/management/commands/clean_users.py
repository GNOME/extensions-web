import datetime

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db.models import Count


User = get_user_model()

class Command(BaseCommand):
    help = 'Clean users'

    def handle(self, *args, **options):
        deleted, _ = User.objects \
            .filter(is_active=False) \
            .filter(date_joined__lte=datetime.date.today() - datetime.timedelta(days=5)) \
            .annotate(extensions_count=Count('extension')).filter(extensions_count=0) \
            .delete()

        self.stdout.write(
            self.style.SUCCESS('Dropped %s users' % deleted)
        )
