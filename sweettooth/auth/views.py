from datetime import datetime, timedelta
from smtplib import SMTPRecipientsRefused
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import PasswordResetConfirmView
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext as _
from django.views.generic.base import TemplateView

from sweettooth.extensions.models import Extension, ExtensionVersion

from .forms import DeleteAccountForm, ProfileForm

User = get_user_model()


def profile(request, user):
    userobj = get_object_or_404(User, username=user)

    is_editable = (request.user == userobj) or request.user.has_perm(
        "review.can-review-extensions"
    )

    display_name = userobj.get_full_name() or userobj.username
    extensions = Extension.objects.visible().filter(creator=userobj).order_by("name")

    if is_editable:
        unreviewed = ExtensionVersion.objects.unreviewed().filter(
            extension__creator=userobj
        )
        waiting = ExtensionVersion.objects.waiting().filter(extension__creator=userobj)
    else:
        unreviewed = []
        waiting = []

    return render(
        request,
        "profile/profile.html",
        dict(
            user=userobj,
            display_name=display_name,
            extensions=extensions,
            unreviewed=unreviewed,
            waiting=waiting,
        ),
    )


@login_required
def profile_redirect(request):
    return redirect("auth-profile", user=request.user.username)


class EmainChangeCancelTokenGenerator:
    SALT = "current-email-salt"
    MAX_AGE = timedelta(days=7)

    def check_token(self, user, token: str):
        if not (user and token):
            return False

        try:
            self.data = TimestampSigner(salt=self.SALT).unsign_object(
                token, max_age=self.MAX_AGE
            )

            return user.pk == self.data["user_id"]
        except BadSignature:
            return False


class EmailChangeCancelView(PasswordResetConfirmView):
    token_generator = EmainChangeCancelTokenGenerator()
    title = _("Restore email and reset password")

    def form_valid(self, form: Any) -> HttpResponse:
        form.user.email = self.token_generator.data["email"]
        form.user.last_email_change = None
        return super().form_valid(form)


class EmailChangeConfirmView(TemplateView):
    SALT = "new-email-salt"
    MAX_AGE = timedelta(days=3)

    template_name = "profile/email_confirm.html"

    def get(
        self, request: HttpRequest, user_id: int, signature: str, *args, **kwargs
    ) -> HttpResponse:
        user = User.objects.get(pk=user_id)
        message = _("Your email address updated successfully")
        try:
            data = TimestampSigner(salt=f"{self.SALT}:{user.password}").unsign_object(
                signature, max_age=self.MAX_AGE
            )

            if data["user_id"] != int(user_id):
                raise BadSignature()

            user.email = data["email"]
            user.save()
        except SignatureExpired:
            message = _("Your confirmation link expired. Please request new one.")
        except BadSignature:
            message = _("Wrong request")

        self.extra_context = {"message": message}
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)


class SettingsView(LoginRequiredMixin, TemplateView):
    template_name = "profile/settings.html"

    MESSAGE_PROFILE_SAVED = _("Profile data saved")

    @staticmethod
    def _schedule_delete_context(schedule_delete: datetime | None) -> dict[str, Any]:
        return {
            "schedule_delete": schedule_delete,
            "schedule_delete_after": (
                schedule_delete + timedelta(days=7) if schedule_delete else None
            ),
        }

    @staticmethod
    def _send_settings_mail(
        subject_template: str, message_template: str, to: str, data: dict[str, Any]
    ):
        subject = (
            render_to_string(f"profile/{subject_template}.txt", data)
            .strip()
            .replace("\n", "")
            .replace("\r", "")
        )

        message = render_to_string(f"profile/{message_template}.txt", data).strip()

        # Never do like this
        # I just don't want to add Celery until redesign version
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to],
        )

    def _notify_user(self, user):
        self._send_settings_mail(
            "account_removal_subject",
            "account_removal_mail",
            user.email,
            {
                "username": user.username,
                "schedule_delete": user.schedule_delete,
            },
        )

    def _send_email_change_current(self, request: HttpRequest, user, new_email: str):
        self._send_settings_mail(
            "change_email_subject",
            "change_email_current_mail",
            user.email,
            {
                "username": user.username,
                "new_email": new_email,
                "cancel_email_change_url": request.build_absolute_uri(
                    reverse(
                        "email_change_cancel",
                        kwargs={
                            "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
                            "token": TimestampSigner(
                                salt=EmainChangeCancelTokenGenerator.SALT
                            ).sign_object(
                                {
                                    "user_id": user.pk,
                                    "email": user.email,
                                }
                            ),
                        },
                    )
                ),
            },
        )

    def _send_email_change_new(self, request: HttpRequest, user: str, email: str):
        self._send_settings_mail(
            "change_email_subject",
            "change_email_new_mail",
            email,
            {
                "username": user.username,
                "confirm_email_change_url": request.build_absolute_uri(
                    reverse(
                        "email_change_confirm",
                        kwargs={
                            "user_id": user.pk,
                            "signature": TimestampSigner(
                                salt=f"{EmailChangeConfirmView.SALT}:{user.password}"
                            ).sign_object(
                                {
                                    "user_id": user.pk,
                                    "email": email,
                                }
                            ),
                        },
                    )
                ),
            },
        )

    def _initial_context(self, user):
        return {
            "delete_account_form": DeleteAccountForm(
                initial={
                    "delete_account": "True" if user.schedule_delete else "False",
                }
            ),
            "profile_form": ProfileForm(instance=user),
        } | self._schedule_delete_context(user.schedule_delete)

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.extra_context = self._initial_context(request.user)
        return super().get(request, *args, **kwargs)

    @transaction.atomic
    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not request.user.is_authenticated:
            return HttpResponseForbidden()

        if request.POST.get("profile_form"):
            return self._profile_post(request)
        else:
            return self._delete_account_post(request)

    def _profile_post(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        messages: list[str] = []

        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            messages.append(self.MESSAGE_PROFILE_SAVED)

            if form.new_email:
                self._send_email_change_new(request, request.user, form.new_email)
                try:
                    self._send_email_change_current(
                        request, request.user, form.new_email
                    )
                except SMTPRecipientsRefused:
                    # Don't fail in case current email is unavailable
                    pass

                request.user.last_email_change = datetime.now()
                messages.append(
                    _(
                        "Confirmation mail is sent to your new address."
                        " Please check your inbox."
                    )
                )

            form.save()

        self.extra_context = self._initial_context(request.user) | {
            "profile_form": form,
            "profile_messages": messages,
        }
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def _delete_account_post(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        schedule_delete = request.user.schedule_delete
        form = DeleteAccountForm(request.POST)
        if form.is_valid():
            request.user.schedule_delete = (
                datetime.now() if form.cleaned_data["delete_account"] else None
            )

            if form.cleaned_data["delete_account"] and not request.user.check_password(
                form.cleaned_data["current_password"]
            ):
                form.add_error("current_password", _("Password is wrong"))
            else:
                request.user.save()

                if form.cleaned_data["delete_account"]:
                    self._notify_user(request.user)

                return render(
                    request,
                    "profile/account-removal.html",
                    {"schedule_delete": request.user.schedule_delete},
                )

        self.extra_context = (
            self._initial_context(request.user)
            | {"delete_account_form": form}
            | self._schedule_delete_context(schedule_delete)
        )
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)
