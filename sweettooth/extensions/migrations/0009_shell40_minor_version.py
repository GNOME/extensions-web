from django.db import migrations, models


def apply(apps, schema_editor):
    ShellVersion = apps.get_model("extensions", "ShellVersion")
    ExtensionVersion = apps.get_model("extensions", "ExtensionVersion")
    all_shell_versions = ShellVersion.objects.all()

    for shell_version in all_shell_versions.filter(major__gte=40).filter(point__gte=0):
        try:
            right_version = all_shell_versions.get(
                major=shell_version.major, minor=shell_version.minor, point=-1
            )
            for extension_version in ExtensionVersion.objects.all().filter(
                shell_versions=shell_version
            ):
                extension_version.shell_versions.remove(shell_version)
                extension_version.shell_versions.add(right_version)
                extension_version.save()

            shell_version.delete()
        except ExtensionVersion.DoesNotExist:
            pass

    all_shell_versions.filter(major__gte=40).filter(point__gte=0).update(point=-1)

    ShellVersion.objects.all().filter(major__gte=40).filter(minor__lt=0).update(
        minor=models.F("minor") - 1
    )


def revert(apps, schema_editor):
    ShellVersion = apps.get_model("extensions", "ShellVersion")

    ShellVersion.objects.all().filter(major__gte=40).filter(minor__lt=-1).update(
        minor=models.F("minor") + 1
    )


class Migration(migrations.Migration):
    dependencies = [
        ("extensions", "0008_auto_20210225_1248"),
    ]

    operations = [
        migrations.RunPython(apply, revert),
    ]
