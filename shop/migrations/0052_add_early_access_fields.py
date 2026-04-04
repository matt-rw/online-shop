# Generated manually for early access site lock feature

from django.db import migrations, models


def add_columns_if_not_exist(apps, schema_editor):
    """Add columns only if they don't already exist (handles partial migrations)."""
    from django.db import connection

    with connection.cursor() as cursor:
        # Get existing columns
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'shop_sitesettings'
        """)
        existing_columns = {row[0] for row in cursor.fetchall()}

        # Add each column if it doesn't exist
        if 'early_access_enabled' not in existing_columns:
            cursor.execute("""
                ALTER TABLE shop_sitesettings
                ADD COLUMN early_access_enabled BOOLEAN DEFAULT FALSE NOT NULL
            """)

        if 'early_access_code' not in existing_columns:
            cursor.execute("""
                ALTER TABLE shop_sitesettings
                ADD COLUMN early_access_code VARCHAR(50) DEFAULT '' NOT NULL
            """)

        if 'early_access_include_staff' not in existing_columns:
            cursor.execute("""
                ALTER TABLE shop_sitesettings
                ADD COLUMN early_access_include_staff BOOLEAN DEFAULT FALSE NOT NULL
            """)

        if 'early_access_launch_at' not in existing_columns:
            cursor.execute("""
                ALTER TABLE shop_sitesettings
                ADD COLUMN early_access_launch_at TIMESTAMP WITH TIME ZONE NULL
            """)


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0051_add_archive_fields"),
    ]

    operations = [
        migrations.RunPython(add_columns_if_not_exist, migrations.RunPython.noop),
    ]
