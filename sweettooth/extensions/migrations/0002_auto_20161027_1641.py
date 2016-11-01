# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import autoslug.fields


class Migration(migrations.Migration):

    dependencies = [
        ('extensions', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='extension',
            name='slug',
            field=autoslug.fields.AutoSlugField(populate_from=b'name', editable=False),
        ),
    ]
