from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin
from django.contrib.auth.models import Group, Permission
from django.db.models import Q

from .models import User

user_fieldsets = list(DefaultUserAdmin.fieldsets)
user_fieldsets[0] = (
    None,
    {"fields": ("username", "password", "schedule_delete", "force_review")},
)
user_fieldsets[1] = (user_fieldsets[1][0], {"fields": ("display_name", "email")})


class CanReviewExtensionsFilter(admin.SimpleListFilter):
    title = "can review extensions"
    parameter_name = "can_review_extensions"

    def lookups(self, request, model_admin):
        return [("1", "Yes"), ("0", "No")]

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset

        perm = Permission.objects.get(
            codename="can-review-extensions", content_type__app_label="review"
        )
        groups = Group.objects.filter(permissions=perm)
        reviewer_filter = (
            Q(is_superuser=True) | Q(user_permissions=perm) | Q(groups__in=groups)
        )

        if self.value() == "1":
            return queryset.filter(reviewer_filter).distinct()

        return queryset.exclude(reviewer_filter).distinct()


@admin.register(User)
class UserAdmin(DefaultUserAdmin):
    fieldsets = user_fieldsets
    list_display = ("username", "email", "display_name", "is_staff")
    search_fields = ("username", "display_name", "email")
    list_filter = (*DefaultUserAdmin.list_filter, CanReviewExtensionsFilter)
