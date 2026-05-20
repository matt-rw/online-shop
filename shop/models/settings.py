from django.core.cache import cache
from django.db import models


class Currency(models.Model):
    """
    Supported currencies for international pricing.
    Prices are stored in USD and converted for display using exchange rates.
    """

    SYMBOL_POSITION_CHOICES = [
        ('before', 'Before amount (e.g., $10)'),
        ('after', 'After amount (e.g., 10€)'),
    ]

    code = models.CharField(
        max_length=3,
        unique=True,
        help_text="ISO 4217 currency code (e.g., USD, EUR, GBP)"
    )
    name = models.CharField(
        max_length=100,
        help_text="Full currency name (e.g., US Dollar, Euro)"
    )
    symbol = models.CharField(
        max_length=10,
        help_text="Currency symbol (e.g., $, €, £, CA$)"
    )
    symbol_position = models.CharField(
        max_length=10,
        choices=SYMBOL_POSITION_CHOICES,
        default='before',
        help_text="Position of symbol relative to amount"
    )
    exchange_rate = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=1,
        help_text="Exchange rate from USD (e.g., 0.92 for EUR means 1 USD = 0.92 EUR)"
    )
    decimal_places = models.PositiveSmallIntegerField(
        default=2,
        help_text="Number of decimal places to display"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this currency is available for selection"
    )
    display_order = models.PositiveIntegerField(
        default=0,
        help_text="Order in currency selector (lower = first)"
    )
    rate_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the exchange rate was last updated"
    )

    class Meta:
        ordering = ['display_order', 'code']
        verbose_name = "Currency"
        verbose_name_plural = "Currencies"

    def __str__(self):
        return f"{self.code} - {self.name}"

    def format_price(self, amount):
        """Format an amount in this currency."""
        from decimal import Decimal, ROUND_HALF_UP

        # Convert from USD to this currency
        converted = Decimal(str(amount)) * self.exchange_rate

        # Round to the appropriate decimal places
        quantize_str = '0.' + '0' * self.decimal_places if self.decimal_places > 0 else '1'
        rounded = converted.quantize(Decimal(quantize_str), rounding=ROUND_HALF_UP)

        # Format the number
        if self.decimal_places > 0:
            formatted_number = f"{rounded:,.{self.decimal_places}f}"
        else:
            formatted_number = f"{int(rounded):,}"

        # Apply symbol position
        if self.symbol_position == 'after':
            return f"{formatted_number}{self.symbol}"
        return f"{self.symbol}{formatted_number}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Invalidate currency cache when settings change
        cache.delete("available_currencies")
        cache.delete("currency_context")

    @classmethod
    def refresh_rates_if_stale(cls, max_age_hours=1):
        """
        Fetch fresh exchange rates from API if rates are stale.
        Caches the API response for 1 hour to avoid excessive requests.
        Returns True if rates were updated, False otherwise.
        """
        import logging
        import requests
        from decimal import Decimal
        from django.utils import timezone
        from datetime import timedelta

        logger = logging.getLogger(__name__)

        # Check cache first - don't fetch if we recently did
        cache_key = "exchange_rates_last_fetch"
        last_fetch = cache.get(cache_key)
        if last_fetch:
            return False  # Already fetched recently

        # Check if any currency needs updating
        stale_threshold = timezone.now() - timedelta(hours=max_age_hours)
        stale_currencies = cls.objects.filter(
            is_active=True,
            rate_updated_at__lt=stale_threshold
        ).exclude(code='USD') | cls.objects.filter(
            is_active=True,
            rate_updated_at__isnull=True
        ).exclude(code='USD')

        if not stale_currencies.exists():
            return False  # All rates are fresh

        # Fetch from API
        api_url = "https://api.exchangerate-api.com/v4/latest/USD"
        try:
            response = requests.get(api_url, timeout=5)
            response.raise_for_status()
            data = response.json()
            rates = data.get('rates', {})

            if not rates:
                return False

            # Update stale currencies
            now = timezone.now()
            updated = 0
            for currency in stale_currencies:
                if currency.code in rates:
                    currency.exchange_rate = Decimal(str(rates[currency.code]))
                    currency.rate_updated_at = now
                    currency.save(update_fields=['exchange_rate', 'rate_updated_at'])
                    updated += 1

            # Cache that we fetched (prevent repeated calls for 1 hour)
            cache.set(cache_key, True, 3600)

            if updated > 0:
                logger.info(f"Auto-refreshed {updated} exchange rates")
                # Clear currency cache so new rates are used
                cache.delete("available_currencies")

            return updated > 0

        except Exception as e:
            logger.warning(f"Failed to auto-refresh exchange rates: {e}")
            # Cache the failure too, so we don't spam the API
            cache.set(cache_key, True, 300)  # Wait 5 min before retry
            return False


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

    # News ticker settings
    news_ticker = models.JSONField(
        default=dict, blank=True,
        help_text="News ticker settings: enabled, text, background_color, text_color, speed"
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
    warehouse_email = models.EmailField(
        blank=True,
        help_text="Warehouse contact email"
    )
    warehouse_latitude = models.FloatField(
        null=True, blank=True,
        help_text="Warehouse latitude (auto-populated from address)"
    )
    warehouse_longitude = models.FloatField(
        null=True, blank=True,
        help_text="Warehouse longitude (auto-populated from address)"
    )

    def geocode_warehouse(self):
        """Geocode warehouse address and save coordinates."""
        from shop.utils.geocoding import geocode_address
        if self.warehouse_city and self.warehouse_state:
            coords = geocode_address(
                self.warehouse_city,
                self.warehouse_state,
                self.warehouse_zip,
                self.warehouse_country or 'US'
            )
            if coords:
                self.warehouse_latitude, self.warehouse_longitude = coords
                self.save(update_fields=['warehouse_latitude', 'warehouse_longitude'])
            return coords
        return None

    # Default shipping weight for products without weight set
    default_product_weight_oz = models.DecimalField(
        max_digits=6, decimal_places=2, default=8,
        help_text="Default product weight in ounces (used when product has no weight set)"
    )

    # Default product image (shown when a product has no images)
    default_product_image = models.URLField(
        blank=True,
        help_text="URL of default image shown when a product has no images (leave empty to show nothing)"
    )

    # Default tax rate for in-person/manual sales (percentage, e.g., 8.25 for 8.25%)
    default_tax_rate = models.DecimalField(
        max_digits=5, decimal_places=3, default=0,
        help_text="Default tax rate percentage for in-person sales (e.g., 8.25 for 8.25%)"
    )

    # Lookbook settings
    lookbook_pages = models.JSONField(
        default=list, blank=True,
        help_text="Lookbook pages. Each page has: image_url, title, description, products (optional)"
    )
    lookbook_settings = models.JSONField(
        default=dict, blank=True,
        help_text="Lookbook settings: is_published, transition_type, etc."
    )

    # About page settings
    about_settings = models.JSONField(
        default=dict, blank=True,
        help_text="About page settings: banner_image, main_text, quote, etc."
    )

    # Early access / site lock settings
    early_access_enabled = models.BooleanField(
        default=False,
        help_text="Enable site lock - visitors must enter code to access the site"
    )
    early_access_code = models.CharField(
        max_length=50, blank=True,
        help_text="Access code visitors must enter to unlock the site"
    )
    early_access_include_staff = models.BooleanField(
        default=False,
        help_text="If enabled, staff/admin users must also enter the code (useful for testing)"
    )
    early_access_launch_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Optional: Site automatically unlocks at this time (leave empty to disable)"
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
