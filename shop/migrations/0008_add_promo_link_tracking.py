from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0007_quick_message_drafts'),
    ]

    operations = [
        migrations.AddField(
            model_name='discount',
            name='link_destination',
            field=models.CharField(
                blank=True,
                choices=[
                    ('', 'No Link'),
                    ('home', 'Home Page'),
                    ('products', 'All Products'),
                    ('custom', 'Custom URL'),
                ],
                default='',
                help_text='Where the promotion link should go',
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name='discount',
            name='link_clicks',
            field=models.IntegerField(
                default=0,
                help_text='Number of times the promotion link has been clicked',
            ),
        ),
        migrations.AlterField(
            model_name='discount',
            name='landing_url',
            field=models.URLField(
                blank=True,
                help_text="Custom landing page URL (only used if destination is 'Custom URL')",
            ),
        ),
    ]
