from datetime import datetime, timedelta

from django import template
from django_comments import get_form
from django_comments.templatetags.comments import RenderCommentFormNode

from ..forms import RatingCommentForm

register = template.Library()


class RenderCaptchaCommentFormNode(RenderCommentFormNode):
    def get_form(self, context):
        obj = self.get_object(context)
        user = context.request.user
        form_class = get_form()

        if user.comment_comments.count() > 10 and (
            datetime.now() - user.date_joined
        ) > timedelta(days=10):
            form_class = RatingCommentForm

        return form_class(obj)


@register.tag
def render_rating_form(parser, token):
    return RenderCaptchaCommentFormNode.handle_token(parser, token)
