
from django.conf.urls import patterns, url

from errorreports import views

urlpatterns = patterns('',
    url(r'^report/(?P<pk>\d+)', views.report_error),
    url(r'^view/(?P<pk>\d+)', views.view_error_report),
)
