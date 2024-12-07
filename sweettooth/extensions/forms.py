# SPDX-License-Identifer: AGPL-3.0-or-later

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
