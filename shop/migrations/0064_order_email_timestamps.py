# Generated manually for email tracking timestamps

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0063_sitesettings_default_product_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='confirmation_email_sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='shipping_email_sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
