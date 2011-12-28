
from django import forms

class UploadForm(forms.Form):
    source = forms.FileField()
    gplv2_compliant = forms.BooleanField(label="""
I verify that my extension can be distributed under the terms of the GPLv2+
""".strip())
    tos_compliant = forms.BooleanField(label="""
I agree that GNOME Shell Extensions can remove, modify or reassign maintainership of my extension
""".strip())
