from django.http import HttpResponseRedirect
from rest_framework import renderers, status

from .models import ExtensionVersion


class ExtensionVersionZipRenderer(renderers.BaseRenderer):
    media_type = "application/zip"
    format = "zip"
    render_style = "binary"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        instance = data.serializer.instance if hasattr(data, "serializer") else None
        if isinstance(instance, ExtensionVersion):
            redirect = HttpResponseRedirect(redirect_to=instance.source.url)
            renderer_context["response"].status_code = redirect.status_code
            renderer_context["response"].headers = redirect.headers
            renderer_context["response"].url = redirect.url

            instance.extension.downloads += 1
            instance.extension.save()
        else:
            renderer_context["response"].status_code = status.HTTP_406_NOT_ACCEPTABLE

        return b""
