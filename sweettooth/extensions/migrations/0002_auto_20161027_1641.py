# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import autoslug.fields
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("extensions", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="extension",
            name="slug",
            field=autoslug.fields.AutoSlugField(populate_from=b"name", editable=False),
        ),
    ]
