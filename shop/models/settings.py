from django.db import models


class SiteSettings(models.Model):
    """
    Global site settings and configuration.
    Should only have one instance (singleton pattern).
    """

    # Hero/Homepage settings
    hero_image = models.ImageField(
        upload_to="site/hero/", blank=True, null=True, help_text="Main hero image for the homepage"
    )
    hero_title = models.CharField(
        max_length=200, default="Welcome to Blueprint", help_text="Main headline on homepage"
    )
    hero_subtitle = models.TextField(blank=True, help_text="Subheadline or description on homepage")

    # Site metadata
    site_name = models.CharField(max_length=100, default="Blueprint Apparel")
    site_description = models.TextField(blank=True)

    # Contact info
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)

    # Social media
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    discord_url = models.URLField(blank=True)

    # Feature flags
    maintenance_mode = models.BooleanField(
        default=False, help_text="Enable to show maintenance page to non-staff users"
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"

    def __str__(self):
        return "Site Settings"

    def save(self, *args, **kwargs):
        # Ensure only one instance exists (singleton)
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        """Get or create the singleton settings instance."""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
