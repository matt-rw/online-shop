# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0062_order_free_shipping_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='default_product_image',
            field=models.URLField(
                blank=True,
                help_text='URL of default image shown when a product has no images (leave empty to show nothing)'
            ),
        ),
    ]
