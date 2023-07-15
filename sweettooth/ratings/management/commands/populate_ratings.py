import datetime
import random

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand, CommandError

from sweettooth.extensions import models
from sweettooth.ratings.models import RatingComment


class Command(BaseCommand):
    help = "Populates all the Extensions with a number of randomly generated ratings."

    def add_arguments(self, parser):
        parser.add_argument("number_of_ratings", nargs=1, type=int)
        parser.add_argument(
            "--user",
            type=str,
            default=None,
            help="Specify the User that creates the rating(s).",
        )

    def _write_rating(self, user=None, verbose=False):
        """Post a randomly generated rating into all the
        extensions. If a user is provided, attempt to post
        the ratings with it as the author.

        Args:
            user (str, optional): Username for the ratings author.
            verbose (bool, optional): Wheter to display extra output.

        Raises:
            CommandError: This exception is raised when the given
                          user does not exist.
        """
        lorem_text = (
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod"
            " tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim"
            " veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea"
            " commodo consequat. Duis aute irure dolor in reprehenderit in voluptate"
            " velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint"
            " occaecat cupidatat non proident, sunt in culpa qui officia deserunt"
            " mollit anim id est laborum."
        )
        lorem_text_list = (lorem_text.replace(",", "")).split()

        random_name = lorem_text_list[random.randint(0, len(lorem_text_list) - 1)]
        current_site = Site.objects.get_current()

        UserModel = get_user_model()
        for extension in models.Extension.objects.all():
            if not user:
                try:
                    user = UserModel.objects.get(username=random_name)
                except UserModel.DoesNotExist:
                    user = UserModel.objects.create_user(
                        username=random_name,
                        email="%s@%s" % (random_name, current_site.domain),
                        password="password",
                    )
            else:
                try:
                    user = UserModel.objects.get(username=user)
                except ObjectDoesNotExist:
                    raise CommandError(
                        "The specified username (%s) does not exist." % user
                    )

            rating_text = lorem_text[: random.randint(1, len(lorem_text))]

            comment = RatingComment(
                user=user,
                content_type=ContentType.objects.get_for_model(extension),
                object_pk=extension._get_pk_val(),
                comment=rating_text,
                rating=random.randint(-1, 5),
                submit_date=datetime.datetime.now(),
                site_id=settings.SITE_ID,
                is_public=True,
                is_removed=False,
            )

            comment.save()

            if verbose:
                self.stdout.write(
                    "\nAdding Rating in Extension:\n%s\n%s\n"
                    % (extension, comment.get_as_text())
                )

    def handle(self, *args, **options):
        verbose = False
        if options["verbosity"] >= 2:
            verbose = True

        number_of_ratings = options["number_of_ratings"][0]

        if verbose:
            self.stdout.write(
                "Generating %d rating(s) for each Extension." % number_of_ratings
            )

        if number_of_ratings <= 0:
            raise CommandError(
                "The number of ratings (%d) provided is not valid." % number_of_ratings
            )

        for ratings in range(0, number_of_ratings):
            if options["user"]:
                self._write_rating(user=options["user"], verbose=verbose)
            else:
                self._write_rating(verbose=verbose)

        if verbose:
            self.stdout.write(self.style.SUCCESS("Done!"))
