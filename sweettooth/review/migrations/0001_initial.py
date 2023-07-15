# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("extensions", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CodeReview",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("date", models.DateTimeField(auto_now_add=True)),
                ("comments", models.TextField(blank=True)),
                (
                    "new_status",
                    models.PositiveIntegerField(
                        null=True,
                        choices=[
                            (0, "Unreviewed"),
                            (1, "Rejected"),
                            (2, "Inactive"),
                            (3, "Active"),
                            (4, "Waiting for author"),
                        ],
                    ),
                ),
                ("auto", models.BooleanField(default=False)),
                (
                    "reviewer",
                    models.ForeignKey(
                        on_delete=models.CASCADE, to=settings.AUTH_USER_MODEL
                    ),
                ),
                (
                    "version",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="reviews",
                        to="extensions.ExtensionVersion",
                    ),
                ),
            ],
            options={
                "permissions": (
                    ("can-review-extensions", "Can review extensions"),
                    ("trusted", "Trusted author"),
                ),
            },
            bases=(models.Model,),
        ),
    ]
