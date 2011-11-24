
import hashlib
import urllib

from jingo import register
from jinja2.utils import Markup

from sorl.thumbnail.shortcuts import get_thumbnail

GRAVATAR_BASE = "https://secure.gravatar.com/avatar/%s?%s"

@register.function
def paginator_html(page_obj, context=3):
    number = page_obj.number
    context_left = range(max(number-context, 2), number)
    context_right = range(number+1, min(number+context+1, page_obj.paginator.num_pages+1))

    lines = []

    if page_obj.has_previous():
        lines.append(u'<a class="number first" href="?page=1">1</a>')
        if number-context > 2:
            lines.append(u'<span class="ellipses">...</span>')

        for i in context_left:
            lines.append(u'<a class="prev number" href="?page=%d">%d</a>' % (i, i))

    lines.append(u'<span class="current number">%d</span>' % (number,))

    if page_obj.has_next():
        for i in context_right:
            lines.append(u'<a class="next number" href="?page=%d">%d</a>' % (i, i))

    return Markup(u'\n'.join(lines))

@register.function
def gravatar_url(email, size=70, default="http://planet.gnome.org/heads/nobody.png"):
    email_md5 = hashlib.md5(email.lower()).hexdigest()
    options = urllib.urlencode(dict(d=default, s=size))
    return GRAVATAR_BASE % (email_md5, options)

@register.function
def thumbnail(field, geometry):
    return get_thumbnail(field, geometry)
