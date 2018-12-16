
from django.conf.urls import url

from sweettooth.errorreports import views

urlpatterns = [
    url(r'^report/(?P<pk>\d+)', views.report_error, name='report_error'),
    url(r'^view/(?P<pk>\d+)', views.view_error_report),
]
