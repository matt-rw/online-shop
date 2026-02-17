# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0028_add_missing_discount_utm_columns'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='is_test',
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text='Test orders created via Test Center'
            ),
        ),
    ]
