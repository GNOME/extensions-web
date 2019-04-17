import uuid
import random

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from sweettooth.extensions import models


class Command(BaseCommand):
    help = 'Populates the database with randomly generated extensions.'

    def add_arguments(self, parser):
        parser.add_argument('number_of_extensions', nargs='+', type=int)
        parser.add_argument(
            '--user',
            type=str,
            default=None,
            help='Specify the User that creates the extension(s).'
        )

    def _create_extension(self, user=None, verbose=False):
        metadata = {}

        metadata.setdefault('uuid', str(uuid.uuid4()))
        metadata.setdefault('name', 'Test Extension {}'.format(random.randint(1, 9999)))
        metadata.setdefault('description', 'Simple test metadata')
        metadata.setdefault('url', 'http://test-metadata.gnome.org')

        if not user:
            random_int = random.randint(1, 9999)
            user = User.objects.create_user(
                username="randomuser{}".format(random_int),
                email='randomuser{}@email.com'.format(random_int),
                password='password'
            )
        else:
            user = User.objects.filter(username=user).first()

            if not user:
                raise CommandError('The specified username does not exist.')

        extension = models.Extension.objects.create_from_metadata(metadata,
                                                                  creator=user)

        extension_version = models.ExtensionVersion.objects.create(extension=extension,
                                                         status=models.STATUS_ACTIVE)
        if verbose:
            self.stdout.write("Created extension {}".format(metadata))

    def handle(self, *args, **options):
        verbose = False
        if options['verbosity'] >= 2:
            verbose = True

        if verbose:
            self.stdout.write("Generating {} extensions.".format(options['number_of_extensions'][0]))

        if options['number_of_extensions'][0] <= 0:
            raise CommandError('The number of extensions ({}) provided is not valid.'.format(options['number_of_extensions'][0]))

        for extension in range(1, options['number_of_extensions'][0]):
            if options['user']:
                self._create_extension(user=options['user'], verbose=verbose)
            else:
                self._create_extension(verbose=verbose)

        if verbose:
            self.stdout.write(self.style.SUCCESS("Done!"))
