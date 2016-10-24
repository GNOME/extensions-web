
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.core.urlresolvers import reverse
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.template import Context
from django.template.loader import render_to_string

from sweettooth.errorreports.models import ErrorReport, error_reported
from sweettooth.errorreports.forms import ErrorReportForm
from sweettooth.extensions.models import Extension

from sweettooth.decorators import model_view

@model_view(Extension.objects.visible())
def report_error(request, extension):
    if request.method == 'POST':
        form = ErrorReportForm(data=request.POST)

        if not request.user.is_authenticated():
            return HttpResponseForbidden()

        if form.is_valid():
            report = form.save(request=request, extension=extension)
            error_reported.send(sender=request, request=request,
                                extension=extension, report=report)

            messages.info(request, "Thank you for your error report!")

            return redirect('extensions-detail',
                            pk=extension.pk,
                            slug=extension.slug)
    else:
        form = ErrorReportForm()

    context = dict(extension=extension,
                   form=form)
    return render(request, 'errorreports/report.html', context)

def can_see_reporter_email(user, report):
    if user.is_superuser:
        return True

    if user in (report.user, report.extension.creator):
        return True

    return False

@login_required
@model_view(ErrorReport)
def view_error_report(request, obj):
    return render(request, 'errorreports/view.html', dict(report=obj,
                                                          show_email=can_see_reporter_email(request.user, obj)))

def send_email_on_error_reported(sender, request, extension, report, **kwargs):
    url = request.build_absolute_uri(reverse('sweettooth.errorreports.views.view_error_report',
                                             kwargs=dict(pk=report.pk)))

    data = dict(extension=extension,
                report=report,
                url=url)

    subject = render_to_string('errorreports/report_mail_subject.txt', data, Context(autoescape=False))
    subject = subject.strip()
    subject = subject.replace('\n', '')
    subject = subject.replace('\r', '')

    message = render_to_string('errorreports/report_mail.txt', data, Context(autoescape=False))
    message = message.strip()

    send_mail(subject=subject,
              message=message,
              from_email=settings.DEFAULT_FROM_EMAIL,
              recipient_list=[extension.creator.email])

error_reported.connect(send_email_on_error_reported)
