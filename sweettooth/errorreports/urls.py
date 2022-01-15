
from django.urls import re_path

from sweettooth.errorreports import views

urlpatterns = [
    re_path(r'^report/(?P<pk>\d+)', views.report_error, name='report_error'),
    re_path(r'^view/(?P<pk>\d+)', views.view_error_report),
]
