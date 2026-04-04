# Fix for partially applied migration - adds missing early_access_launch_at column

from django.db import migrations


def add_launch_at_if_missing(apps, schema_editor):
    """Add early_access_launch_at column if it doesn't exist."""
    from django.db import connection

    db_vendor = connection.vendor

    with connection.cursor() as cursor:
        if db_vendor == 'sqlite':
            # SQLite: use PRAGMA to check columns
            cursor.execute("PRAGMA table_info(shop_sitesettings)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'early_access_launch_at' not in columns:
                cursor.execute("""
                    ALTER TABLE shop_sitesettings
                    ADD COLUMN early_access_launch_at DATETIME NULL
                """)
        else:
            # PostgreSQL: use information_schema
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
