# Generated manually for early access site lock feature

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0051_add_archive_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitesettings",
            name="early_access_enabled",
            field=models.BooleanField(
                default=False,
                help_text="Enable site lock - visitors must enter code to access the site",
            ),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="early_access_code",
            field=models.CharField(
                blank=True,
                max_length=50,
                help_text="Access code visitors must enter to unlock the site",
            ),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="early_access_include_staff",
            field=models.BooleanField(
                default=False,
                help_text="If enabled, staff/admin users must also enter the code (useful for testing)",
            ),
        ),
    ]
