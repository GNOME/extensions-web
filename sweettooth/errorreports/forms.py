
from django import forms

from sweettooth.errorreports.models import ErrorReport

class ErrorReportForm(forms.ModelForm):

    comment = forms.CharField(widget=forms.Textarea())

    class Meta:
        model = ErrorReport
        fields = ('comment',)

    def clean_comment(self):
        return self.cleaned_data['comment'].strip()

    def save(self, request, extension, commit=True):
        report = super().save(commit=False)
        report.user = request.user
        report.extension = extension
        if commit:
            report.save()
        return report

