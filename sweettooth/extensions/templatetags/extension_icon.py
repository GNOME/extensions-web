from django import template

register = template.Library()


@register.simple_tag
def extension_icon(icon):
    return icon.url if icon else "/static/images/plugin.png"
