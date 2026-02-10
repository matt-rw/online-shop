# Generated manually for shipment tracking on OrderItem

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0016_add_bundle_use_component_pricing'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderitem',
            name='shipment_item',
            field=models.ForeignKey(
                blank=True,
                help_text='The shipment batch this item was allocated from',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='order_items',
                to='shop.shipmentitem',
            ),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='unit_cost',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Cost per unit at time of sale (from shipment)',
                max_digits=10,
                null=True,
            ),
        ),
    ]
