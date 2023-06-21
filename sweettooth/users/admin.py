from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin
from django.utils.translation import gettext as _

from .models import User


user_fieldsets = list(DefaultUserAdmin.fieldsets)
user_fieldsets[0] = (None, {'fields': ('username', 'password', 'schedule_delete', 'force_review')})
user_fieldsets[1] = (user_fieldsets[1][0], {'fields': ('display_name', 'email')})


class UserAdmin(DefaultUserAdmin):
    fieldsets = user_fieldsets
    list_display = ('username', 'email', 'display_name', 'is_staff')
    search_fields = ('username', 'display_name', 'email')


admin.site.register(User, UserAdmin)
