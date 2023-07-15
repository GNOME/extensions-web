from sweettooth.extensions.models import ExtensionVersion


def n_unreviewed_extensions(request):
    if not request.user.has_perm("review.can-review-extensions"):
        return dict()

    return dict(n_unreviewed_extensions=ExtensionVersion.objects.unreviewed().count())
