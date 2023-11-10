from captcha.fields import ReCaptchaField
from captcha.widgets import ReCaptchaV2Checkbox
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.forms import fields, widgets
from django.utils import timezone
from django.utils.encoding import force_str
from django_comments.forms import CommentForm

from sweettooth.ratings.models import RatingComment


# Raty inserts its own <input> element, so we don't want to provide
# a widget here. We'll insert a <div> for raty to fill in the template.
class NoOpWidget(widgets.Widget):
    def render(self, *a, **kw):
        return ""


class RatingCommentForm(CommentForm):
    rating = fields.IntegerField(
        min_value=-1, max_value=5, required=False, widget=NoOpWidget()
    )
    name = None
    email = None
    url = None

    def clean_rating(self):
        rating = self.cleaned_data["rating"]
        if not rating:
            rating = 0
        return rating

    def get_comment_model(self):
        return RatingComment

    def get_comment_create_data(self, site_id=None):
        return dict(
            content_type=ContentType.objects.get_for_model(self.target_object),
            object_pk=force_str(self.target_object._get_pk_val()),
            comment=self.cleaned_data["comment"],
            rating=self.cleaned_data["rating"],
            submit_date=timezone.now(),
            site_id=site_id or getattr(settings, "SITE_ID", None),
            is_public=True,
            is_removed=False,
        )


class RatingCaptchaCommentForm(RatingCommentForm):
    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox)
