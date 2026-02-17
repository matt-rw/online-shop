from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0030_return_returnitem"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitesettings",
            name="slideshow_settings",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Slideshow settings: duration, transition, autoplay",
            ),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="gallery_images",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Gallery images below products. Each has: image_url, alt_text",
            ),
        ),
    ]
