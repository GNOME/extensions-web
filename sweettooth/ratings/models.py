from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django_comments.managers import CommentManager
from django_comments.models import Comment
from django_comments.signals import comment_will_be_posted

from ..extensions.models import Extension


class RatingComment(Comment):
    objects = CommentManager()

    rating = models.IntegerField(
        default=0,
        validators=[
            MaxValueValidator(5),
            MinValueValidator(0),
        ],
    )


def make_sure_user_was_authenticated(sender, comment, request, **kwargs):
    return request.user.is_authenticated


comment_will_be_posted.connect(make_sure_user_was_authenticated)


@receiver(post_save, sender=RatingComment)
def update_rating(
    sender: type[RatingComment], instance: RatingComment, created: bool, **kwargs
):
    if created and isinstance(instance.content_object, Extension):
        extension = instance.content_object
        extension.rated += 1
        extension.rating = (
            extension.rating * (extension.rated - 1) + instance.rating
        ) / extension.rated
        extension.save()
