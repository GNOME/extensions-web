import json

from django.apps.registry import Apps
from django.db import migrations, models

from sweettooth.extensions.models import ExtensionVersion as ExtensionVersionModel
from sweettooth.extensions.models import SessionMode as SessionModeModel


def apply(apps: Apps, schema_editor):
    ExtensionVersion: ExtensionVersionModel = apps.get_model(
        "extensions", "ExtensionVersion"
    )
    SessionMode: SessionModeModel = apps.get_model("extensions", "SessionMode")

    for mode in SessionModeModel.SessionModes.values:
        SessionMode.objects.create(mode=mode)

    for version in ExtensionVersion.objects.all():
        metadata = json.loads(version.extra_json_fields)
        session_modes = [
            SessionMode.objects.get(pk=mode)
            for mode in metadata.get("session-modes", [])
        ]

        if session_modes:
            version.session_modes.set(session_modes)
            version.save()


def revert(apps: Apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("extensions", "0009_shell40_minor_version"),
    ]

    operations = [
        migrations.CreateModel(
            name="SessionMode",
            fields=[
                (
                    "mode",
                    models.CharField(
                        choices=[
                            ("user", "User"),
                            ("unlock-dialog", "Unlock Dialog"),
                            ("gdm", "Gdm"),
                        ],
                        max_length=16,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="extensionversion",
            name="session_modes",
            field=models.ManyToManyField(to="extensions.SessionMode"),
        ),
        migrations.RunPython(apply, revert),
    ]
