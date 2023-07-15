from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def paginator(page_obj, context=3):
    number = page_obj.number
    num_pages = page_obj.paginator.num_pages
    context_left = range(max(number - context, 2), number)
    context_right = range(number + 1, min(number + context + 1, num_pages))

    lines = []

    if page_obj.has_previous():
        lines.append(
            '<a class="number prev" href="?page=%d">Previous</a>' % (number - 1,)
        )
        lines.append('<a class="number first" href="?page=1">1</a>')
        if number - context > 2:
            lines.append('<span class="ellipses">...</span>')

        for i in context_left:
            lines.append('<a class="prev number" href="?page=%d">%d</a>' % (i, i))

    lines.append('<span class="current number">%d</span>' % (number,))

    if page_obj.has_next():
        for i in context_right:
            lines.append('<a class="next number" href="?page=%d">%d</a>' % (i, i))

        if num_pages - (number + context) > 1:
            lines.append('<span class="ellipses">...</span>')

        lines.append(
            '<a class="number first" href="?page=%d">%d</a>' % (num_pages, num_pages)
        )
        lines.append('<a class="number prev" href="?page=%d">Next</a>' % (number + 1,))

    return mark_safe("\n".join(lines))
