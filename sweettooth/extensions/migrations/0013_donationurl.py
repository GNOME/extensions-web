# Generated by Django 3.2.18 on 2023-04-13 17:59

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('extensions', '0012_extensionversion_extension_id__status_idx'),
    ]

    operations = [
        migrations.CreateModel(
            name='DonationUrl',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('url_type', models.CharField(choices=[('buymeacoffee', 'Buy Me a Coffee'), ('custom', 'Custom URL'), ('github', 'GitHub Sponsors'), ('ko_fi', 'Ko-fi'), ('patreon', 'Patreon'), ('paypal', 'PayPal')], default='custom', max_length=32)),
                ('url', models.CharField(max_length=256)),
                ('extension', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='donation_urls', to='extensions.extension')),
            ],
        ),
    ]