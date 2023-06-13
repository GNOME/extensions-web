from datetime import datetime, timedelta
from typing import Any, Optional
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import send_mail
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic.base import TemplateView
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
from django.utils.translation import gettext as _

from .forms import DeleteAccountForm
from sweettooth.extensions.models import Extension, ExtensionVersion

from sweettooth.decorators import ajax_view


def profile(request, user):
    userobj = get_object_or_404(get_user_model(), username=user)

    is_editable = (request.user == userobj) or request.user.has_perm('review.can-review-extensions')

    display_name = userobj.get_full_name() or userobj.username
    extensions = Extension.objects.visible().filter(creator=userobj).order_by('name')

    if is_editable:
        unreviewed = ExtensionVersion.objects.unreviewed().filter(extension__creator=userobj)
        waiting = ExtensionVersion.objects.waiting().filter(extension__creator=userobj)
    else:
        unreviewed = []
        waiting = []

    return render(request,
                  'profile/profile.html',
                  dict(user=userobj,
                       display_name=display_name,
                       extensions=extensions,
                       unreviewed=unreviewed,
                       waiting=waiting,
                       is_editable=is_editable))


@ajax_view
@require_POST
@login_required
def ajax_change_display_name(request, pk):
    if request.POST['id'] != 'new_display_name':
        return HttpResponseForbidden()

    userobj = get_object_or_404(get_user_model(), pk=pk)
    is_editable = (request.user == userobj) or request.user.has_perm('review.can-review-extensions')

    if not is_editable:
        return HttpResponseForbidden()

    # display name is "%s %s" % (first_name, last_name). Change the first name.
    userobj.first_name = request.POST['value']
    userobj.save()
    return userobj.first_name


@login_required
def profile_redirect(request):
    return redirect('auth-profile', user=request.user.username)


class SettingsView(LoginRequiredMixin, TemplateView):
    template_name = 'profile/settings.html'

    @staticmethod
    def _schedule_delete_context(schedule_delete: Optional[datetime]) -> dict[str, Any]:
        return {
            'schedule_delete': schedule_delete,
            'schedule_delete_after': (
                schedule_delete + timedelta(days=7) if schedule_delete else None
            ),
        }

    @staticmethod
    def _notify_user(user):
        # Never do like this
        # I just don't want to add Celery until redesign version
        data = {
            'username': user.username,
            'schedule_delete': user.schedule_delete
        }

        subject = render_to_string('profile/account_removal_subject.txt', data) \
            .strip() \
            .replace('\n', '') \
            .replace('\r', '')

        message = render_to_string('profile/account_removal_mail.txt', data).strip()

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email]
        )

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.extra_context = {
            'delete_account_form': DeleteAccountForm(initial={
                'delete_account': "True" if request.user.schedule_delete else "False",
            }),
        } | self._schedule_delete_context(request.user.schedule_delete)
        return super().get(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not request.user.is_authenticated:
            return HttpResponseForbidden()

        form = DeleteAccountForm(request.POST)
        schedule_delete = request.user.schedule_delete
        if form.is_valid():
            request.user.schedule_delete = datetime.now() if form.cleaned_data['delete_account'] else None

            if form.cleaned_data['delete_account'] and not request.user.check_password(form.cleaned_data['current_password']):
                form.add_error('current_password', _("Password is wrong"))
            else:
                request.user.save()

                if form.cleaned_data['delete_account']:
                    self._notify_user(request.user)

                return render(request, "profile/account-removal.html", {'schedule_delete': request.user.schedule_delete})

        self.extra_context = {'delete_account_form': form} | self._schedule_delete_context(schedule_delete)
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)
