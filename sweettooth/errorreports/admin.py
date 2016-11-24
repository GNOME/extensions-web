
from django.contrib import admin

from sweettooth.errorreports.models import ErrorReport

class ErrorReportAdmin(admin.ModelAdmin):
    list_display = 'extension', 'user'
    list_display_links = list_display

admin.site.register(ErrorReport, ErrorReportAdmin)
