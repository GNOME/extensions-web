import uuid
import random

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from sweettooth.extensions.models import Extension
from sweettooth.extensions import models


class Command(BaseCommand):
    help = 'Populates the database with randomly generated extensions.'

    def add_arguments(self, parser):
        parser.add_argument('number_of_extensions', nargs='+', type=int)
        parser.add_argument(
            '--creator_user_name',
            type=str,
            default=None
            )

    def _create_extension(self, creator=None):
        metadata = {}

        metadata.setdefault('uuid', str(uuid.uuid4()))
        metadata.setdefault('name', 'Test Extension {}'.format(random.randint(1, 9999)))
        metadata.setdefault('description', 'Simple test metadata')
        metadata.setdefault('url', 'http://test-metadata.gnome.org')

        if not creator:
            random_int = random.randint(1, 9999)
            user = User.objects.create_user(username="randomuser{}".format(random_int),
                                             email='randomuser{}@email.com'.format(random_int),
                                             password='password')
        else:
            user = User.objects.filter(username=creator).first()

        extension = models.Extension.objects.create_from_metadata(metadata,
                                                                  creator=user)

        version = models.ExtensionVersion.objects.create(extension=extension,
                                                         status=models.STATUS_ACTIVE)
        print("Created extension {}".format(metadata))

    def handle(self, *args, **options):
        print("Options are: {}".format(options))
        for extension in range(1, options['number_of_extensions'][0]):
            if options['creator_user_name']:
                self._create_extension(creator=options['creator_user_name'][0])
            else:
                self._create_extension()