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

        # Add link_destination if missing
        if 'link_destination' not in existing_columns:
            cursor.execute("""
                ALTER TABLE shop_discount
                ADD COLUMN link_destination VARCHAR(50) DEFAULT '' NOT NULL
            """)

        # Add link_clicks if missing
        if 'link_clicks' not in existing_columns:
            cursor.execute("""
                ALTER TABLE shop_discount
                ADD COLUMN link_clicks INTEGER DEFAULT 0 NOT NULL
            """)

        # Add landing_url if missing
        if 'landing_url' not in existing_columns:
            cursor.execute("""
                ALTER TABLE shop_discount
                ADD COLUMN landing_url VARCHAR(200) DEFAULT '' NOT NULL
            """)


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0010_alter_quickmessage_options_and_more'),
    ]

    operations = [
        migrations.RunPython(add_missing_columns, migrations.RunPython.noop),
    ]
