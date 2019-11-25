
from django.forms import fields, widgets
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django_comments.forms import CommentForm
from django.utils.encoding import force_text
from django.utils.safestring import mark_safe
from django.utils import timezone

from sweettooth.ratings.models import RatingComment

# Raty inserts its own <input> element, so we don't want to provide
# a widget here. We'll insert a <div> for raty to fill in the template.
class NoOpWidget(widgets.Widget):
    def render(self, *a, **kw):
        return u''

class RatingCommentForm(CommentForm):
    rating = fields.IntegerField(min_value=-1, max_value=5,
                                 required=False, widget=NoOpWidget())

    def clean_rating(self):
        rating = self.cleaned_data["rating"]
        if rating is None:
            rating = -1
        return rating

    def get_comment_model(self):
        return RatingComment

    def get_comment_create_data(self, site_id=None):
        return dict(
            content_type = ContentType.objects.get_for_model(self.target_object),
            object_pk    = force_text(self.target_object._get_pk_val()),
            comment      = self.cleaned_data["comment"],
            rating       = self.cleaned_data["rating"],
            submit_date  = timezone.now(),
            site_id      = site_id or getattr(settings, "SITE_ID", None),
            is_public    = True,
            is_removed   = False,
        )

# Remove the URL, name and email fields. We don't want them.
RatingCommentForm.base_fields.pop('url')
RatingCommentForm.base_fields.pop('name')
RatingCommentForm.base_fields.pop('email')
