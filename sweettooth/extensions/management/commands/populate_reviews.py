import uuid
import random

from django.core.management.base import BaseCommand
from sweettooth.extensions import models


class Command(BaseCommand):
    help = 'Populates all the Extensions reviews with randomly generated ratings.'

    def add_arguments(self, parser):
        parser.add_argument('number_of_reviews', nargs='+', type=int)
        parser.add_argument(
            '--user',
            type=str,
            default=None,
            help='Specify the User that creates the extension(s).'
        )

    def _write_review(self, creator=None, verbose=False):
        lorem_text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."
        lorem_text_list = (lorem_text.replace(',', '')).split()

        review_text = lorem_text[:random.randint(1, len(lorem_text))]

        random_name = lorem_text_list[random.randint(0, len(lorem_text_list))]

        # if not creator:
        #     user = User.objects.create_user(username=random_name,
        #                              email='{}@email.com'.format(random_name),
        #                              password='password')
        # else:
        #     user = models.User.objects.filter(username=creator).first()

        #     if not user:
        #         raise CommandError('The specified username {} does not exist.'.format(creator))


        from django_comments.forms import CommentForm
        dict(
                    content_type = ContentType.objects.get_for_model(self.target_object),
                    object_pk    = force_text(self.target_object._get_pk_val()),
                    comment      = self.cleaned_data["comment"],
                    rating       = self.cleaned_data["rating"],
                    submit_date  = datetime.datetime.now(),
                    site_id      = settings.SITE_ID,
                    is_public    = True,
                    is_removed   = False,
                )
        for extension in models.Extension.objects.all():
            print(entensions)

    def handle(self, *args, **options):
        verbose = False
        if options['verbosity'] >= 2:
            verbose = True

        #if verbose:
        self.stdout.write("Generating {} reviews.".format(options['number_of_reviews'][0]))

        if options['number_of_reviews'][0] <= 0 :
            raise CommandError('The number of reviews ({}) provided is not valid.'.format(options['number_of_reviews'][0]))

        for reviews in range(1, options['number_of_reviews'][0]):
            if options['user']:
                self._write_review(creator=options['user'], verbose=verbose)
            else:
                self._write_review(verbose=verbose)

        #if verbose:
        self.stdout.write(self.style.SUCCESS("Done!"))
