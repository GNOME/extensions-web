
from django import forms

class UploadForm(forms.Form):
    source = forms.FileField()
    gplv2_compliant = forms.BooleanField(label="""
I verify that my extension can be distributed under the terms of the GPLv2+
""".strip())
