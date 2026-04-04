# Sync migration state - fields already exist in database from earlier migrations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0056_sitesettings_early_access_code_and_more"),
    ]

    operations = [
        # Use SeparateDatabaseAndState to update Django's state without touching DB
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="sitesettings",
                    name="early_access_code",
                    field=models.CharField(
                        blank=True,
                        help_text="Access code visitors must enter to unlock the site",
                        max_length=50,
                    ),
                ),
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
                    name="early_access_include_staff",
                    field=models.BooleanField(
                        default=False,
                        help_text="If enabled, staff/admin users must also enter the code (useful for testing)",
                    ),
                ),
                migrations.AddField(
                    model_name="sitesettings",
                    name="early_access_launch_at",
                    field=models.DateTimeField(
                        blank=True,
                        help_text="Optional: Site automatically unlocks at this time (leave empty to disable)",
                        null=True,
                    ),
                ),
            ],
            database_operations=[],  # Don't touch the database - fields already exist
        ),
    ]
