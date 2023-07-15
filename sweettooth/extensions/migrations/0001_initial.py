# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import autoslug.fields
from django.conf import settings
from django.db import migrations, models

import sweettooth.extensions.models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Extension",
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
                ("name", models.CharField(max_length=200)),
                ("uuid", models.CharField(unique=True, max_length=200, db_index=True)),
                ("slug", autoslug.fields.AutoSlugField(editable=False)),
                ("description", models.TextField(blank=True)),
                ("url", models.URLField(blank=True)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("downloads", models.PositiveIntegerField(default=0)),
                ("popularity", models.IntegerField(default=0)),
                (
                    "screenshot",
                    models.ImageField(
                        upload_to=sweettooth.extensions.models.make_screenshot_filename,
                        blank=True,
                    ),
                ),
                (
                    "icon",
                    models.ImageField(
                        default=b"/static/images/plugin.png",
                        upload_to=sweettooth.extensions.models.make_icon_filename,
                        blank=True,
                    ),
                ),
                (
                    "creator",
                    models.ForeignKey(
                        on_delete=models.CASCADE, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            options={
                "permissions": (("can-modify-data", "Can modify extension data"),),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="ExtensionPopularityItem",
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
                ("offset", models.IntegerField()),
                ("date", models.DateTimeField(auto_now_add=True)),
                (
                    "extension",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="popularity_items",
                        to="extensions.Extension",
                    ),
                ),
            ],
            options={},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="ExtensionVersion",
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
                ("version", models.IntegerField(default=0)),
                ("extra_json_fields", models.TextField()),
                (
                    "status",
                    models.PositiveIntegerField(
                        choices=[
                            (0, "Unreviewed"),
                            (1, "Rejected"),
                            (2, "Inactive"),
                            (3, "Active"),
                            (4, "Waiting for author"),
                        ]
                    ),
                ),
                (
                    "source",
                    models.FileField(
                        max_length=223,
                        upload_to=sweettooth.extensions.models.make_filename,
                    ),
                ),
                (
                    "extension",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="versions",
                        to="extensions.Extension",
                    ),
                ),
            ],
            options={
                "get_latest_by": "version",
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="ShellVersion",
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
                ("major", models.PositiveIntegerField()),
                ("minor", models.PositiveIntegerField()),
                ("point", models.IntegerField()),
            ],
            options={},
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name="extensionversion",
            name="shell_versions",
            field=models.ManyToManyField(to="extensions.ShellVersion"),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name="extensionversion",
            unique_together=set([("extension", "version")]),
        ),
    ]
