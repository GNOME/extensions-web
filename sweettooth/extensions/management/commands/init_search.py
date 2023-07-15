from django.core.management.base import BaseCommand
from django_opensearch_dsl.registries import registry


class Command(BaseCommand):
    help = "Create missing search indexes"

    def handle(self, *args, **options):
        indices = registry.get_indices()

        for index in indices:
            if not index.exists():
                index.create()
