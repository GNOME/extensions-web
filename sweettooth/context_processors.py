def navigation(request):
    return {
        'global_menu': [
            {
                'id': 'extensions-index',
                'name': 'Extensions'
            },
            {
                'id': 'extensions-upload-file',
                'name': 'Add yours'
            },
            {
                'id': 'extensions-local',
                'name': 'Installed extensions'
            },
            {
                'id': 'extensions-about',
                'name': 'About'
            }
        ]
    }
