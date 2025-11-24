# Migration to fix production database state
# This migration was originally used to fix an older production database state
# It's now a no-op since 0001_initial creates all necessary tables

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0001_initial'),
    ]

    operations = [
        # No-op - 0001_initial now contains all required schema
        # This migration is kept to maintain the migration chain for databases
        # that may have already applied it
    ]
