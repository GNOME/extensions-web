"""
    GNOME Shell Extensions Repository
    Copyright (C) 2011 Jasper St. Pierre <jstpierre@mecheye.net>
    Copyright (C) 2020 Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""

from django import forms
from django.core.validators import FileExtensionValidator

from .form_fields import RestrictedImageField

class UploadForm(forms.Form):
    source = forms.FileField(required=True)
    gplv2_compliant = forms.BooleanField(label="""
I verify that my extension can be distributed under the terms of the GPLv2+
""".strip(), required=False)

    tos_compliant = forms.BooleanField(label="""
I agree that GNOME Shell Extensions can remove, modify or reassign maintainership of my extension
""".strip(), required=False)

    def clean_gplv2_compliant(self):
        gplv2_compliant = self.cleaned_data['gplv2_compliant']
        if not gplv2_compliant:
            raise forms.ValidationError("You must be able to distribute your extension under the terms of the GPLv2+.")
        return gplv2_compliant

    def clean_tos_compliant(self):
        tos_compliant = self.cleaned_data['tos_compliant']
        if not tos_compliant:
            raise forms.ValidationError("You must agree to the GNOME Shell Extensions terms of service.")
        return tos_compliant


class ImageUploadForm(forms.Form):
    allowed_types = ["gif", "jpg", "jpeg", "png", "webp"]
    file = RestrictedImageField(
        required=True,
        allowed_types=allowed_types,
        validators=[FileExtensionValidator(allowed_types)]
    )
