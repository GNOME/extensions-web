# SPDX-License-Identifer: AGPL-3.0-or-later

from contextlib import suppress

from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django_opensearch_dsl import Document, fields
from django_opensearch_dsl.registries import registry
from opensearchpy.helpers.analysis import analyzer

from .models import Extension, ExtensionVersion


@registry.register_document
class ExtensionDocument(Document):
    class Index:
        name = "extensions"
        settings = {
            "analysis": {
                "filter": {
                    "edge_ngram_filter": {
                        "type": "edge_ngram",
                        "min_gram": 3,
                        "max_gram": 12,
                    }
                },
                "analyzer": {
                    "autocomplete": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": ["lowercase", "edge_ngram_filter"],
                    }
                },
            },
        }

    class Django:
        model = Extension

        fields = [
            "uuid",
            "description",
            "created",
            "updated",
            "downloads",
            "popularity",
            "recommended",
        ]

    name = fields.TextField(
        fields={"raw": fields.KeywordField()},
        analyzer=analyzer("autocomplete"),
    )
    creator = fields.TextField(
        analyzer=analyzer("autocomplete"),
    )
    shell_versions = fields.TextField(multi=True)

    def get_queryset(self, *args, **kwargs):
        return super().get_queryset(*args, **kwargs).select_related("creator")

    def prepare_creator(self, extension):
        return extension.creator.get_full_name()

    def prepare_shell_versions(self, extension):
        return list(extension.visible_shell_version_map.keys())

    def should_index_object(self, extension):
        return extension.latest_version

    @staticmethod
    def document_fields():
        return ["uuid", "name", "description", "creator"]


@receiver(post_delete, sender=ExtensionVersion)
@receiver(post_save, sender=ExtensionVersion)
def index_on_version_save(instance, **kwargs):
    with suppress(Extension.DoesNotExist):
        if instance.extension.latest_version:
            ExtensionDocument().update(instance.extension, action="index")
        else:
            try:
                ExtensionDocument().update(instance.extension, action="delete")
            except Exception as ex:
                errors = getattr(ex, "errors", [])
                if (
                    not errors
                    or not isinstance(errors[0], dict)
                    or errors[0].get("delete", {}).get("result", "") != "not_found"
                ):
                    raise ex


@receiver(post_delete, sender=get_user_model())
@receiver(post_save, sender=get_user_model())
def index_on_user_save(instance, **kwargs):
    extensions = Extension.objects.visible().filter(creator=instance)
    ExtensionDocument().update(extensions, action="index")
