import random
import datetime

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.contrib.contenttypes.models import ContentType
from django.conf import settings

from sweettooth.extensions import models
from sweettooth.ratings.models import RatingComment


class Command(BaseCommand):
    help = 'Populates all the Extensions with a number of randomly generated reviews.'

    def add_arguments(self, parser):
        parser.add_argument('number_of_reviews', nargs='+', type=int)
        parser.add_argument(
            '--user',
            type=str,
            default=None,
            help='Specify the User that creates the review(s).'
        )

    def _write_review(self, user=None, verbose=False):
        lorem_text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."
        lorem_text_list = (lorem_text.replace(',', '')).split()

        review_text = lorem_text[:random.randint(1, len(lorem_text))]

        random_name = lorem_text_list[random.randint(0, len(lorem_text_list)-1)]

        for extension in models.Extension.objects.all():

            if verbose:
                 self.stdout.write("Adding Comment in Extension:\n{}".format(extension))

            if not user:
                user = models.User.objects.filter(username=random_name).first()

                if not user:
                    user = User.objects.create_user(
                        username=random_name,
                        email='{}@email.com'.format(random_name),
                        password='password'
                    )
            else:
                user = models.User.objects.filter(username=user).first()

            if not user:
                raise CommandError('The specified username does not exist.')

            comment = RatingComment(
                user=user,
                content_type=ContentType.objects.get_for_model(extension),
                object_pk=extension._get_pk_val(),
                comment=review_text,
                rating=random.randint(-1, 5),
                submit_date=datetime.datetime.now(),
                site_id=settings.SITE_ID,
                is_public=True,
                is_removed=False,
            )

            comment.save()

            if verbose:
                 self.stdout.write("Adding Comment:\n{}".format(comment.get_as_text()))

    def handle(self, *args, **options):
        verbose = False
        if options['verbosity'] >= 2:
            verbose = True

        if verbose:
            self.stdout.write("Generating {} review(s).".format(options['number_of_reviews'][0]))

        if options['number_of_reviews'][0] <= 0 :
            raise CommandError('The number of reviews ({}) provided is not valid.'.format(options['number_of_reviews'][0]))

        for reviews in range(0, options['number_of_reviews'][0]):
            if options['user']:
                self._write_review(user=options['user'], verbose=verbose)
            else:
                self._write_review(verbose=verbose)

        if verbose:
            self.stdout.write(self.style.SUCCESS("Done!"))
