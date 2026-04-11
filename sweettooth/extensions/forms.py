# SPDX-License-Identifer: AGPL-3.0-or-later

from django import forms
from django.core.validators import FileExtensionValidator

from .form_fields import RestrictedImageField


class ImageUploadForm(forms.Form):
    allowed_types = ["gif", "jpg", "jpeg", "png", "webp"]
    file = RestrictedImageField(
        required=True,
        allowed_types=allowed_types,
        validators=[FileExtensionValidator(allowed_types)],
    )
