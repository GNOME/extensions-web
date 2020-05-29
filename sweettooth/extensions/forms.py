
from django import forms

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
    file = forms.ImageField(required=True)
