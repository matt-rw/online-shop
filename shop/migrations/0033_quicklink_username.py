from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0032_alter_order_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='quicklink',
            name='username',
            field=models.CharField(blank=True, help_text='Username or email used for this service (for reference)', max_length=150),
        ),
    ]
