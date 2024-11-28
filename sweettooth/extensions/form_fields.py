# SPDX-License-Identifer: AGPL-3.0-or-later

from django.core.exceptions import ValidationError
from django.forms.fields import ImageField


class RestrictedImageField(ImageField):
    def __init__(self, *, allowed_types=["gif", "jpeg", "png", "webp"], **kwargs):
        self.allowed_types = allowed_types
        super().__init__(**kwargs)

    def to_python(self, data):
        f = super().to_python(data)
        if f is None or f.image is None:
            return None

        if f.image.format is None or f.image.format.lower() not in self.allowed_types:
            raise ValidationError(
                self.error_messages["invalid_image"],
                code="invalid_image_type",
            )

        if hasattr(f, "seek") and callable(f.seek):
            f.seek(0)

        return f
