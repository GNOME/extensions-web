
from jingo import register
from jinja2.utils import Markup

from django.contrib.comments import Comment, get_form
from django.contrib.contenttypes.models import ContentType

from django.template.loader import render_to_string

@register.function
def rating(value, out_of):
    parts = []
    for i in xrange(out_of):
        attrs = u' disabled'
        if value == i:
            attrs += u' checked'
        parts.append(u'<input type="radio"%s>' % (attrs,))
    return Markup(u'\n'.join(parts))

@register.function
def get_comments(model):
    return Comment.objects.for_model(model)

@register.function
def render_comment_form(obj):
    ctype = ContentType.objects.get_for_model(obj)
    template_search_list = [
        "comments/%s/%s/form.html" % (ctype.app_label, ctype.model),
        "comments/%s/form.html" % ctype.app_label,
        "comments/form.html"
        ]
    return Markup(render_to_string(template_search_list, {"form" : get_form()(obj) }))
