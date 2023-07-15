from sweettooth.auth import forms


def login_form(request):
    if request.user.is_authenticated:
        return {}

    return dict(login_popup_form=forms.InlineAuthenticationForm())
