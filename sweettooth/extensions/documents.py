"""
    GNOME Shell extensions repository
    Copyright (C) 2020  Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from django_opensearch_dsl import Document, fields
from django_opensearch_dsl.registries import registry

from .models import Extension, ExtensionVersion


@registry.register_document
class ExtensionDocument(Document):
    class Index:
        name = 'extensions'

    class Django:
        model = Extension

        fields = [
            'uuid',
            'description',
            'created',
            'downloads',
            'popularity',
        ]

    name = fields.TextField(
        fields={'raw': fields.KeywordField()},
    )
    creator = fields.TextField()
    shell_versions = fields.TextField(multi=True)

    def get_queryset(self, *args, **kwargs):
        return super(ExtensionDocument, self).get_queryset(*args, **kwargs).select_related(
            'creator'
        )

    def prepare_creator(self, extension):
        return extension.creator.get_full_name()

    def prepare_shell_versions(self, extension):
        return list(extension.visible_shell_version_map.keys())

    def should_index_object(self, extension):
        return extension.latest_version

    @staticmethod
    def document_fields():
        return ['uuid', 'name', 'description', 'creator']


@receiver(post_delete, sender=ExtensionVersion)
@receiver(post_save, sender=ExtensionVersion)
def index_on_version_save(instance, **kwargs):
    if instance.extension.latest_version:
        ExtensionDocument().update(instance.extension, action='index')
    else:
        try:
            ExtensionDocument().update(instance.extension, action='delete')
        except Exception as ex:
            errors = getattr(ex, 'errors', [])
            if (
                not errors or
                not isinstance(errors[0], dict) or
                errors[0].get('delete', {}).get('result', '') != 'not_found'
            ):
                raise ex
