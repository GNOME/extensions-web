from django.utils.translation import ugettext as _

def navigation(request):
    return {
        'global_menu': [
            {
                'id': 'extensions-index',
                # Translators: Main menu item
                'name': _('Extensions')
            },
            {
                'id': 'extensions-upload-file',
                # Translators: Main menu item
                'name': _('Add yours')
            },
            {
                'id': 'extensions-local',
                # Translators: Main menu item
                'name': _('Installed extensions')
            },
            {
                'id': 'extensions-about',
                # Translators: Main menu item
                'name': _('About')
            }
        ]
    }
