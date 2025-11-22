from django.db import models
from django.utils import timezone


class PageView(models.Model):
    """
    Track individual page views with visitor information.
    """

    # Request Information
    path = models.CharField(max_length=500)
    method = models.CharField(max_length=10, default="GET")

    # Visitor Information
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # Referrer Information
    referrer = models.URLField(max_length=1000, blank=True, null=True)
    referrer_domain = models.CharField(max_length=255, blank=True)

    # Geographic/Device Info
    device_type = models.CharField(max_length=50, blank=True)  # mobile, desktop, tablet, bot
    browser = models.CharField(max_length=100, blank=True)
    os = models.CharField(max_length=100, blank=True)

    # Location data
    country = models.CharField(max_length=2, blank=True)  # ISO country code (US, GB, etc.)
    country_name = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)  # State/Province
    city = models.CharField(max_length=100, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    # Timing
    viewed_at = models.DateTimeField(default=timezone.now, db_index=True)
    response_time_ms = models.IntegerField(null=True, blank=True)

    # Session tracking (optional)
    session_id = models.CharField(max_length=100, blank=True, db_index=True)

    class Meta:
        ordering = ["-viewed_at"]
        indexes = [
            models.Index(fields=["-viewed_at"]),
            models.Index(fields=["path", "-viewed_at"]),
            models.Index(fields=["referrer_domain", "-viewed_at"]),
        ]

    def __str__(self):
        return f"{self.path} - {self.viewed_at.strftime('%Y-%m-%d %H:%M:%S')}"

    @property
    def is_external_referrer(self):
        """Check if referrer is from external domain."""
        if not self.referrer_domain:
            return False
        # Add your domain variations here
        internal_domains = ["localhost", "127.0.0.1", "blueprintapparel.com"]
        return not any(domain in self.referrer_domain for domain in internal_domains)


class VisitorSession(models.Model):
    """
    Aggregate session-level visitor data.
    """

    session_id = models.CharField(max_length=100, unique=True, db_index=True)

    # First visit info
    first_seen = models.DateTimeField(default=timezone.now)
    landing_page = models.CharField(max_length=500)
    referrer = models.URLField(max_length=1000, blank=True, null=True)

    # Last visit info
    last_seen = models.DateTimeField(default=timezone.now)

    # Aggregate stats
    page_views = models.IntegerField(default=1)

    # Visitor info
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_type = models.CharField(max_length=50, blank=True)

    # Location data
    country = models.CharField(max_length=2, blank=True)
    country_name = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["-last_seen"]

    def __str__(self):
        return f"Session {self.session_id[:8]}... - {self.page_views} views"
