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
from .serializers import ExtensionUploadSerializer


class UploadForm(forms.Form):
    source = forms.FileField(required=True)
    shell_license_compliant = forms.BooleanField(
        label=ExtensionUploadSerializer._declared_fields[
            "shell_license_compliant"
        ].label,
        required=False,
    )

    tos_compliant = forms.BooleanField(
        label=ExtensionUploadSerializer._declared_fields["tos_compliant"].label,
        required=False,
    )

    def clean_shell_license_compliant(self):
        shell_license_compliant = self.cleaned_data["shell_license_compliant"]
        if not shell_license_compliant:
            raise forms.ValidationError(ExtensionUploadSerializer.TOS_VALIDATION_ERROR)
        return shell_license_compliant

    def clean_tos_compliant(self):
        tos_compliant = self.cleaned_data["tos_compliant"]
        if not tos_compliant:
            raise forms.ValidationError(ExtensionUploadSerializer.TOS_VALIDATION_ERROR)
        return tos_compliant


class ImageUploadForm(forms.Form):
    allowed_types = ["gif", "jpg", "jpeg", "png", "webp"]
    file = RestrictedImageField(
        required=True,
        allowed_types=allowed_types,
        validators=[FileExtensionValidator(allowed_types)],
    )
