from django.core.cache import cache
from django.db import models


class QuickLink(models.Model):
    """Quick access links to external services (Stripe, Render, GitHub, etc.)"""

    CATEGORY_CHOICES = [
        ('payments', 'Payments'),
        ('hosting', 'Hosting'),
        ('shipping', 'Shipping'),
        ('development', 'Development'),
        ('marketing', 'Marketing'),
        ('analytics', 'Analytics'),
        ('other', 'Other'),
    ]

    name = models.CharField(max_length=100, help_text="Display name (e.g., 'Stripe Dashboard')")
    url = models.URLField(help_text="Full URL to the service")
    icon = models.CharField(
        max_length=50,
        blank=True,
        default='fa-link',
        help_text="FontAwesome icon class (e.g., 'fa-stripe', 'fa-github', 'fa-server')"
    )
    username = models.CharField(
        max_length=150,
        blank=True,
        help_text="Username or email used for this service (for reference)"
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this service"
    )
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='other'
    )
    display_order = models.PositiveIntegerField(default=0, help_text="Lower numbers appear first")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name


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
        max_length=200, default="", blank=True, help_text="Main headline on homepage"
    )
    hero_subtitle = models.TextField(blank=True, help_text="Subheadline or description on homepage")
    hero_slides = models.JSONField(
        default=list, blank=True,
        help_text="Hero slideshow slides. Each slide has: image_url, alt_text, link_url (optional)"
    )
    slideshow_settings = models.JSONField(
        default=dict, blank=True,
        help_text="Slideshow settings: duration, transition, autoplay"
    )
    gallery_images = models.JSONField(
        default=list, blank=True,
        help_text="Gallery images below products. Each has: image_url, alt_text"
    )

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

    # Test/Dev settings
    default_test_email = models.EmailField(
        blank=True, help_text="Default email address for test messages"
    )
    default_test_phone = models.CharField(
        max_length=20, blank=True, help_text="Default phone number for test messages"
    )

    # Bug report notifications
    bug_report_email = models.EmailField(
        blank=True, help_text="Email address for bug report notifications (falls back to contact email)"
    )

    # Warehouse/Shipping settings
    warehouse_name = models.CharField(
        max_length=100, default="Blueprint Apparel",
        help_text="Business name for shipping labels"
    )
    warehouse_street1 = models.CharField(
        max_length=255, blank=True,
        help_text="Warehouse street address line 1"
    )
    warehouse_street2 = models.CharField(
        max_length=255, blank=True,
        help_text="Warehouse street address line 2"
    )
    warehouse_city = models.CharField(
        max_length=100, blank=True,
        help_text="Warehouse city"
    )
    warehouse_state = models.CharField(
        max_length=50, blank=True,
        help_text="Warehouse state/province"
    )
    warehouse_zip = models.CharField(
        max_length=20, blank=True,
        help_text="Warehouse postal code"
    )
    warehouse_country = models.CharField(
        max_length=2, default="US",
        help_text="Warehouse country code (e.g., US)"
    )
    warehouse_phone = models.CharField(
        max_length=20, blank=True,
        help_text="Warehouse phone number"
    )

    # Default shipping weight for products without weight set
    default_product_weight_oz = models.DecimalField(
        max_digits=6, decimal_places=2, default=8,
        help_text="Default product weight in ounces (used when product has no weight set)"
    )

    # Default tax rate for in-person/manual sales (percentage, e.g., 8.25 for 8.25%)
    default_tax_rate = models.DecimalField(
        max_digits=5, decimal_places=3, default=0,
        help_text="Default tax rate percentage for in-person sales (e.g., 8.25 for 8.25%)"
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
        # Invalidate cache when settings change
        cache.delete("site_settings_context")

    @classmethod
    def load(cls):
        """Get or create the singleton settings instance."""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
