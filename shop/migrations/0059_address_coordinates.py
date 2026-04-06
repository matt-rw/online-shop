from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0058_create_admin_order_template'),
    ]

    operations = [
        migrations.AddField(
            model_name='address',
            name='latitude',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='address',
            name='longitude',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='warehouse_latitude',
            field=models.FloatField(blank=True, null=True, help_text='Warehouse latitude (auto-populated from address)'),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='warehouse_longitude',
            field=models.FloatField(blank=True, null=True, help_text='Warehouse longitude (auto-populated from address)'),
        ),
    ]
