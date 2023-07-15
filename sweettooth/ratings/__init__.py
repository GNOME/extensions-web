from django.apps import AppConfig


def get_model():
    from sweettooth.ratings.models import RatingComment

    return RatingComment


def get_form():
    from sweettooth.ratings.forms import RatingCaptchaCommentForm

    return RatingCaptchaCommentForm


class RatingsConfig(AppConfig):
    def ready(self):
        from django_comments.moderation import moderator

        from sweettooth.extensions.models import Extension

        from .moderation import ExtensionCommentsModerator

        moderator.register(Extension, ExtensionCommentsModerator)
