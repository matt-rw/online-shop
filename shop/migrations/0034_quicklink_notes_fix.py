from django.db import migrations, models


def add_notes_if_missing(apps, schema_editor):
    """Add notes column if it doesn't exist (fixes partial migration)."""
    from django.db import connection

    # Check if column exists (works for both PostgreSQL and SQLite)
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM shop_quicklink LIMIT 0")
        columns = [col[0] for col in cursor.description]

        if 'notes' not in columns:
            cursor.execute("ALTER TABLE shop_quicklink ADD COLUMN notes text DEFAULT '' NOT NULL")


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0033_quicklink_username'),
    ]

    operations = [
        migrations.RunPython(add_notes_if_missing, migrations.RunPython.noop),
    ]
