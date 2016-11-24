
import urllib
import hashlib

GRAVATAR_BASE = "https://secure.gravatar.com/avatar/%s?%s"

def gravatar_url(request, email, size=70):
    email_md5 = hashlib.md5(email.lower()).hexdigest()
    options = urllib.urlencode(dict(d="mm", s=size))
    return GRAVATAR_BASE % (email_md5, options)
