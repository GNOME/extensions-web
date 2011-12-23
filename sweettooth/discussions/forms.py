
import datetime

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.comments.forms import CommentForm
from django.utils.encoding import force_unicode

class DiscussionCommentForm(CommentForm):
    def get_comment_create_data(self):
        return dict(
            content_type = ContentType.objects.get_for_model(self.target_object),
            object_pk    = force_unicode(self.target_object._get_pk_val()),
            comment      = self.cleaned_data["comment"],
            submit_date  = datetime.datetime.now(),
            site_id      = settings.SITE_ID,
            is_public    = True,
            is_removed   = False,
        )

# Remove the URL, name and email fields. We don't want them.
DiscussionCommentForm.base_fields.pop('url')
DiscussionCommentForm.base_fields.pop('name')
DiscussionCommentForm.base_fields.pop('email')
