from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin
from django.utils.translation import gettext as _

from .models import User


user_fieldsets = list(DefaultUserAdmin.fieldsets)
user_fieldsets[0] = (None, {'fields': ('username', 'password', 'schedule_delete', 'force_review')})


class UserAdmin(DefaultUserAdmin):
    fieldsets = user_fieldsets


admin.site.register(User, UserAdmin)
