import hashlib
from urllib.parse import urlencode

GRAVATAR_BASE = "https://secure.gravatar.com/avatar/%s?%s"


def gravatar_url(request, email, size=70):
    email_md5 = hashlib.md5(email.lower().encode("utf-8")).hexdigest()
    options = urlencode({"d": "mm", "s": size})
    return GRAVATAR_BASE % (email_md5, options)
