# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_comments", "0003_add_submit_date_index"),
    ]

    operations = [
        migrations.CreateModel(
            name="RatingComment",
            fields=[
                (
                    "comment_ptr",
                    models.OneToOneField(
                        parent_link=True,
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        on_delete=models.CASCADE,
                        to="django_comments.Comment",
                    ),
                ),
                ("rating", models.IntegerField(default=-1, blank=True)),
            ],
            options={
                "ordering": ("submit_date",),
                "abstract": False,
                "verbose_name": "comment",
                "verbose_name_plural": "comments",
                "permissions": [("can_moderate", "Can moderate comments")],
            },
            bases=("django_comments.comment",),
        ),
    ]
