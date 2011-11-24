from django import template
import urllib, hashlib

GRAVATAR_BASE = "https://secure.gravatar.com/avatar/%s?%s"

@register.simple_tag
def gravatar_url(email, size=70, default="http://planet.gnome.org/heads/nobody.png"):
    email_md5 = hashlib.md5(email.lower()).hexdigest()
    options = urllib.urlencode(dict(d=default, s=size))
    return GRAVATAR_BASE % (email_md5, options)
