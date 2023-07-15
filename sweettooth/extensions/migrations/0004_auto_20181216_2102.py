# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from sweettooth.extensions.models import Extension


def update_icons(apps, schema_editor):
    Extension.objects.filter(icon__startswith="/").update(icon="")


class Migration(migrations.Migration):
    dependencies = [
        ("extensions", "0003_auto_20181216_2101"),
    ]

    operations = [migrations.RunPython(update_icons)]
