"""
    GNOME Shell extensions repository
    Copyright (C) 2020  Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""

import logging

from django_elasticsearch_dsl import Document
from django_elasticsearch_dsl.registries import registry

from .models import Extension

# Get an instance of a logger
logger = logging.getLogger(__name__)


@registry.register_document
class ExtensionDocument(Document):
    class Index:
        name = 'extensions'

    class Django:
        model = Extension

        # The fields of the model you want to be indexed in Elasticsearch
        fields = [
            'uuid',
            'name',
            'description',
            'created',
            'updated',
            'downloads',
            'popularity',
        ]

    def get_queryset(self):
        return super(ExtensionDocument, self).get_queryset().select_related(
            'creator'
        )

    def prepare_creator(self, extension):
        return extension.creator.username

    @staticmethod
    def document_fields():
        return ['uuid', 'name', 'description', 'creator']
