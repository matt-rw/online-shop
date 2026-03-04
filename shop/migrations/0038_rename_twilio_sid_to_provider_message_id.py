# Generated migration to rename twilio_sid to provider_message_id

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0037_add_warehouse_and_product_weight'),
    ]

    operations = [
        migrations.RenameField(
            model_name='smslog',
            old_name='twilio_sid',
            new_name='provider_message_id',
        ),
        migrations.AlterField(
            model_name='smslog',
            name='provider_message_id',
            field=models.CharField(blank=True, help_text='Message ID from SMS provider (Telnyx/Twilio)', max_length=64),
        ),
    ]
