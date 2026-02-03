from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0008_add_promo_link_tracking'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='default_test_email',
            field=models.EmailField(blank=True, help_text='Default email address for test messages', max_length=254),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='default_test_phone',
            field=models.CharField(blank=True, help_text='Default phone number for test messages', max_length=20),
        ),
    ]
