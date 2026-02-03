from django.db import migrations


def add_missing_columns(apps, schema_editor):
    """Add missing columns to shop_discount if they don't exist."""
    from django.db import connection

    with connection.cursor() as cursor:
        # Check what columns exist
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'shop_discount'
        """)
        existing_columns = {row[0] for row in cursor.fetchall()}

        # Define all potentially missing columns with their SQL definitions
        missing_columns = {
            'link_destination': "VARCHAR(50) DEFAULT ''",
            'link_clicks': "INTEGER DEFAULT 0 NOT NULL",
            'landing_url': "VARCHAR(200) DEFAULT ''",
            'utm_source': "VARCHAR(100) DEFAULT ''",
            'utm_medium': "VARCHAR(100) DEFAULT ''",
            'utm_campaign': "VARCHAR(100) DEFAULT ''",
            'variant_name': "VARCHAR(100) DEFAULT ''",
            'test_tags': "VARCHAR(500) DEFAULT ''",
        }

        for column_name, column_def in missing_columns.items():
            if column_name not in existing_columns:
                cursor.execute(f"""
                    ALTER TABLE shop_discount
                    ADD COLUMN {column_name} {column_def}
                """)


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0010_alter_quickmessage_options_and_more'),
    ]

    operations = [
        migrations.RunPython(add_missing_columns, migrations.RunPython.noop),
    ]
