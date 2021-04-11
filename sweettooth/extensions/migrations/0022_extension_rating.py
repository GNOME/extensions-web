"""
    GNOME Shell extensions repository
    Copyright (C) 2021  Yuri Konotopov <ykonotopov@gnome.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
"""

from django.db import migrations, models


def populate_data(apps, schema_editor):
    Extension = apps.get_model("extensions", "Extension")
    RatingComment = apps.get_model("ratings", "RatingComment")
    comments = (
        RatingComment.objects.filter(rating__gt=0)
        .values("object_pk")
        .annotate(rating_sum=models.Sum("rating"), rated=models.Count("object_pk"))
        .order_by("object_pk")
    )  # https://code.djangoproject.com/ticket/32546

    for comment in comments:
        if comment.get("rated") and comment.get("rating_sum"):
            try:
                extension = Extension.objects.get(pk=comment.get("object_pk"))
            except Extension.DoesNotExist:
                continue

            extension.rated = comment.get("rated")
            extension.rating = comment.get("rating_sum") / extension.rated

            extension.save()


def revert_data(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("extensions", "0021_extension_recommended"),
        ("ratings", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="extension",
            name="rated",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="extension",
            name="rating",
            field=models.FloatField(default=0),
        ),
        migrations.RunPython(populate_data, revert_data),
    ]
