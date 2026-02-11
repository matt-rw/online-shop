# Generated manually for bundle available_for_purchase field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0017_orderitem_shipment_tracking'),
    ]

    operations = [
        migrations.AddField(
            model_name='bundle',
            name='available_for_purchase',
            field=models.BooleanField(
                default=True,
                help_text='Whether this bundle can be purchased (uncheck for coming soon/preview)',
            ),
        ),
    ]
