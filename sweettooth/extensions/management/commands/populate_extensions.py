import random
import uuid

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand, CommandError

from sweettooth.extensions import models


class Command(BaseCommand):
    help = "Populates the database with randomly generated extensions."

    def add_arguments(self, parser):
        parser.add_argument("number_of_extensions", nargs=1, type=int)
        parser.add_argument(
            "--user",
            type=str,
            default=None,
            help="Specify the User that creates the extension(s).",
        )

    def _create_extension(self, user=None, verbose=False):
        """Create an extension using boilerplate data,
        if a user is provided, attempt to assing it as
        the author of the extension.

        Args:
            user (str, optional): Username for the extension author.
            verbose (bool, optional): Wheter to display extra output.

        Raises:
            CommandError: This exception is raised when the given
                          user does not exist.
        """
        current_site = Site.objects.get_current()
        metadata = {
            "uuid": str(uuid.uuid4()),
            "name": "Test Extension %d" % random.randint(1, 9999),
            "description": "Simple test metadata",
            "url": "%s" % current_site.domain,
        }

        UserModel = get_user_model()
        if not user:
            random_name = "randomuser%d" % random.randint(1, 9999)

            try:
                user = UserModel.objects.get(username=random_name)
            except ObjectDoesNotExist:
                user = UserModel.objects.create_user(
                    username=random_name,
                    email="%s@%s" % (random_name, current_site.domain),
                    password="password",
                )
        else:
            try:
                user = UserModel.objects.get(username=user)
            except ObjectDoesNotExist:
                raise CommandError("The specified username (%s) does not exist." % user)

        extension = models.Extension.objects.create_from_metadata(
            metadata, creator=user
        )

        models.ExtensionVersion.objects.create(
            extension=extension, status=models.STATUS_ACTIVE
        )
        if verbose:
            self.stdout.write("Created extension %s with user %s" % (metadata, user))

    def handle(self, *args, **options):
        verbose = False
        if options["verbosity"] >= 2:
            verbose = True

        number_of_extensions = options["number_of_extensions"][0]

        if verbose:
            self.stdout.write("Generating %d extensions." % number_of_extensions)

        if options["number_of_extensions"][0] <= 0:
            raise CommandError(
                "The number of extensions (%d) provided is not valid."
                % number_of_extensions
            )

        for extension in range(1, number_of_extensions):
            if options["user"]:
                self._create_extension(user=options["user"], verbose=verbose)
            else:
                self._create_extension(verbose=verbose)

        if verbose:
            self.stdout.write(self.style.SUCCESS("Done!"))
