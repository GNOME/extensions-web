from django import template

from sweettooth.utils import gravatar_url

register = template.Library()
register.simple_tag(gravatar_url)
