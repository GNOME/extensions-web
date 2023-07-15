from django.utils.translation import gettext as _


def navigation(request):
    return {
        "global_menu": [
            {"id": "extensions-index", "name": _("Extensions")},
            {"id": "extensions-upload-file", "name": _("Add yours")},
            {"id": "extensions-local", "name": _("Installed extensions")},
            {"id": "extensions-about", "name": _("About")},
        ]
    }
