# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('comments', '__first__'),
    ]

    operations = [
        migrations.CreateModel(
            name='RatingComment',
            fields=[
                ('comment_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='comments.Comment')),
                ('rating', models.IntegerField(default=-1, blank=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('comments.comment',),
        ),
    ]
