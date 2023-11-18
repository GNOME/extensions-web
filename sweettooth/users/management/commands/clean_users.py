import datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from sweettooth.extensions.models import Extension

User = get_user_model()


class Command(BaseCommand):
    help = "Clean users"

    @staticmethod
    def _with_extensions(queryset):
        return queryset.annotate(extensions_count=Count("extensions")).filter(
            extensions_count__gt=0
        )

    @transaction.atomic
    def handle(self, *args, **options):
        maintainer_wanted, _ = User.objects.get_or_create(
            username=settings.MAINTAINER_WANTED_USERNAME
        )
        now = datetime.datetime.now()

        scheduled_users = (
            User.objects.filter(is_active=True)
            .exclude(schedule_delete__isnull=True)
            .filter(schedule_delete__lte=now - datetime.timedelta(days=7))
        )

        inactive_users = User.objects.filter(is_active=False).filter(
            date_joined__lte=now - datetime.timedelta(days=5)
        )

        users_with_extensions = self._with_extensions(
            scheduled_users
        ) | self._with_extensions(inactive_users)
        for user in users_with_extensions:
            Extension.objects.filter(creator=user).update(creator=maintainer_wanted)

        _, scheduled = scheduled_users.delete()
        _, inactive = inactive_users.delete()

        self.stdout.write(
            self.style.SUCCESS(
                "Dropped %d scheduled and %d inactive users"
                % (
                    scheduled.get("users.User", 0),
                    inactive.get("users.User", 0),
                )
            )
        )
