from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0059_address_coordinates'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='exclude_from_stats',
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text='Exclude this order from revenue/profit calculations'
            ),
        ),
    ]
