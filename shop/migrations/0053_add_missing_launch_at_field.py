# Fix for partially applied migration - adds missing early_access_launch_at column

from django.db import migrations


def add_launch_at_if_missing(apps, schema_editor):
    """Add early_access_launch_at column if it doesn't exist."""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'shop_sitesettings' AND column_name = 'early_access_launch_at'
        """)
        if not cursor.fetchone():
            cursor.execute("""
                ALTER TABLE shop_sitesettings
                ADD COLUMN early_access_launch_at TIMESTAMP WITH TIME ZONE NULL
            """)


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0052_add_early_access_fields"),
    ]

    operations = [
        migrations.RunPython(add_launch_at_if_missing, migrations.RunPython.noop),
    ]
