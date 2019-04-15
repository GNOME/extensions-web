import uuid
import random

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from sweettooth.extensions import models


class Command(BaseCommand):
    help = 'Populates all the Extensions reviews with randomly generated Users and ratings.'

    def add_arguments(self, parser):
        parser.add_argument('number_of_reviews', nargs='+', type=int)
        parser.add_argument('number_of_users', nargs='+', type=int)

    def _write_review(self, creator):
        lorem_text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."
        lorem_text_list = (lorem_text.replace(',', '')).split()

        review_text = lorem_text[:random.randint(1, len(lorem_text))]

        random_name = lorem_text_list[random.randint(0, len(lorem_text_list))]

        user = User.objects.create_user(username=random_name,
                                 email='{}@email.com'.format(random_name),
                                 password='password')

        entension = models.Extension.objects.

    def handle(self, *args, **options):
        print("Options are: {}".format(options))
        print("Number of extensions are: {}".format(options['number_of_extensions'][0]))
        print("Creator is: {}".format(options['creator_user_name'][0]))
        for extension in range(1, options['number_of_extensions'][0]):
            self._create_extension(creator=options['creator_user_name'][0])
