# SPDX-License-Identifer: AGPL-3.0-or-later

from django_filters.widgets import QueryArrayWidget as MutableQueryArrayWidget


# https://github.com/carltongibson/django-filter/issues/1047
class QueryArrayWidget(MutableQueryArrayWidget):
    def value_from_datadict(self, data, files, name):
        return super().value_from_datadict(data.copy(), files, name)
