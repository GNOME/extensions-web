"""
    GNOME Shell Extensions Repository
    Copyright (C) 2020 Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""

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

        if f.image.format is None or not f.image.format.lower() in self.allowed_types:
            raise ValidationError(
                self.error_messages["invalid_image"],
                code="invalid_image_type",
            )

        if hasattr(f, "seek") and callable(f.seek):
            f.seek(0)

        return f
