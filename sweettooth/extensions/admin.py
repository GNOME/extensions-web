from django.contrib import admin

from sweettooth.extensions.models import (
    STATUS_ACTIVE,
    STATUS_REJECTED,
    DonationUrl,
    Extension,
    ExtensionVersion,
)
from sweettooth.review.models import CodeReview


class CodeReviewAdmin(admin.TabularInline):
    model = CodeReview
    fields = ("reviewer", "comments")
    raw_id_fields = ("reviewer",)


class ExtensionVersionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "status",
    )
    list_display_links = ("title",)
    actions = (
        "approve",
        "reject",
    )

    def title(self, ver):
        if ver.version_name:
            return "%s (%d, %s)" % (ver.extension.uuid, ver.version, ver.version_name)
        return "%s (%d)" % (ver.extension.uuid, ver.version)

    title.short_description = "Extension (version)"

    inlines = [CodeReviewAdmin]

    def approve(self, request, queryset):
        queryset.update(status=STATUS_ACTIVE)

    def reject(self, request, queryset):
        queryset.update(status=STATUS_REJECTED)


class ExtensionVersionInline(admin.TabularInline):
    model = ExtensionVersion
    fields = (
        "version",
        "status",
    )
    extra = 0


class ExtensionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "uuid",
        "num_versions",
        "creator",
    )
    list_display_links = (
        "name",
        "uuid",
    )
    search_fields = ("uuid", "name")
    raw_id_fields = ("creator",)

    def num_versions(self, ext):
        return ext.versions.count()

    num_versions.short_description = "#V"

    inlines = [ExtensionVersionInline]


@admin.register(DonationUrl)
class DonationAdmin(admin.ModelAdmin):
    pass


admin.site.register(ExtensionVersion, ExtensionVersionAdmin)
admin.site.register(Extension, ExtensionAdmin)
