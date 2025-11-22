from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Campaign(models.Model):
    """
    A marketing campaign containing multiple scheduled email and SMS messages.
    Example: "Fall Sale 2025", "New Customer Welcome Series", "Re-engagement Campaign"
    """

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("paused", "Paused"),
        ("completed", "Completed"),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    # Targeting
    target_group = models.CharField(
        max_length=100, blank=True, help_text="e.g., 'All Subscribers', 'New Customers', 'VIP'"
    )

    # Operating Window
    active_from = models.DateTimeField(
        null=True, blank=True, help_text="Campaign becomes active from this date"
    )
    active_until = models.DateTimeField(
        null=True, blank=True, help_text="Campaign remains active until this date"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="campaigns"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    @property
    def total_messages(self):
        """Total number of messages in this campaign."""
        return self.messages.count()

    @property
    def sent_messages(self):
        """Number of messages that have been sent."""
        return self.messages.filter(status="sent").count()


class CampaignMessage(models.Model):
    """
    A single scheduled message (email or SMS) within a campaign.
    """

    MESSAGE_TYPE_CHOICES = [
        ("email", "Email"),
        ("sms", "SMS"),
        ("instagram", "Instagram"),
        ("tiktok", "TikTok"),
        ("snapchat", "Snapchat"),
        ("youtube", "YouTube"),
        ("promotion", "Promotion"),
        ("product", "Product"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("scheduled", "Scheduled"),
        ("sent", "Sent"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
        ("draft", "Draft"),
    ]

    SEND_MODE_CHOICES = [
        ("auto", "Auto-send"),
        ("draft", "Save as Draft"),
        ("manual", "Manual Approval Required"),
    ]

    TRIGGER_TYPE_CHOICES = [
        ("immediate", "Send Immediately"),
        ("delay", "Send After Delay"),
        ("specific_date", "Send on Specific Date"),
    ]

    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="messages")

    # Message details
    name = models.CharField(
        max_length=200, help_text="e.g., 'Welcome Email', 'Day 3 Follow-up SMS'"
    )
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES)

    # Content - either use a template or custom content
    email_template = models.ForeignKey(
        "EmailTemplate", on_delete=models.SET_NULL, null=True, blank=True
    )
    sms_template = models.ForeignKey(
        "SMSTemplate", on_delete=models.SET_NULL, null=True, blank=True
    )

    # Or custom content (overrides template)
    custom_subject = models.CharField(
        max_length=200, blank=True
    )  # For email or social media caption
    custom_content = models.TextField(blank=True)  # For message body or notes

    # Additional fields for social media and advanced options
    send_mode = models.CharField(
        max_length=20,
        choices=SEND_MODE_CHOICES,
        default="auto",
        help_text="How this message should be sent",
    )
    media_urls = models.TextField(
        blank=True, help_text="URLs for images, videos, or other media (one per line)"
    )
    notes = models.TextField(blank=True, help_text="Internal notes, content ideas, or reminders")

    # Promotion/Discount linking
    discount = models.ForeignKey(
        "Discount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaign_messages",
        help_text="Optional discount to associate with this message",
    )
    products = models.ManyToManyField(
        "Product",
        blank=True,
        related_name="campaign_messages",
        help_text="Specific products this message applies to (optional)",
    )

    # Scheduling
    trigger_type = models.CharField(
        max_length=20, choices=TRIGGER_TYPE_CHOICES, default="immediate"
    )
    delay_days = models.IntegerField(
        default=0, help_text="Days to wait before sending (if trigger_type is 'delay')"
    )
    delay_hours = models.IntegerField(default=0, help_text="Hours to wait before sending")
    scheduled_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Specific date/time to send (if trigger_type is 'specific_date')",
    )

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Stats
    total_recipients = models.IntegerField(default=0)
    sent_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    # Order in campaign
    order = models.IntegerField(
        default=0, help_text="Order of this message in the campaign sequence"
    )

    # URL Tracking for social media and marketing
    landing_url = models.URLField(
        blank=True,
        help_text="Landing page URL for this post/message (e.g., https://site.com/products)",
    )
    utm_source = models.CharField(
        max_length=100,
        blank=True,
        help_text="UTM Source (e.g., instagram, tiktok, email)",
    )
    utm_medium = models.CharField(
        max_length=100, blank=True, help_text="UTM Medium (e.g., social, post, story)"
    )
    utm_campaign = models.CharField(
        max_length=100,
        blank=True,
        help_text="UTM Campaign name (e.g., spring_launch_2025)",
    )
    utm_content = models.CharField(
        max_length=100,
        blank=True,
        help_text="UTM Content (optional, for A/B testing different creatives)",
    )

    # A/B Testing and Performance Tracking
    variant_name = models.CharField(
        max_length=50,
        blank=True,
        help_text="Variant identifier (e.g., 'A', 'B', 'Emoji Version', 'Short Copy')",
    )
    test_tags = models.CharField(
        max_length=255,
        blank=True,
        help_text="Comma-separated tags for testing (e.g., 'emoji,urgency,discount50')",
    )

    # Performance metrics
    clicks = models.IntegerField(
        default=0, help_text="Number of clicks on the tracking URL"
    )
    conversions = models.IntegerField(
        default=0, help_text="Number of conversions (purchases) from this message"
    )
    revenue = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Total revenue generated from this message",
    )

    class Meta:
        ordering = ["campaign", "order", "created_at"]

    def __str__(self):
        return f"{self.campaign.name} - {self.name} ({self.message_type})"

    @property
    def click_through_rate(self):
        """Calculate CTR (clicks / recipients * 100)."""
        if self.total_recipients == 0:
            return 0
        return round((self.clicks / self.total_recipients) * 100, 2)

    @property
    def conversion_rate(self):
        """Calculate conversion rate (conversions / clicks * 100)."""
        if self.clicks == 0:
            return 0
        return round((self.conversions / self.clicks) * 100, 2)

    @property
    def revenue_per_click(self):
        """Calculate revenue per click."""
        if self.clicks == 0:
            return 0
        return round(float(self.revenue) / self.clicks, 2)

    @property
    def revenue_per_recipient(self):
        """Calculate revenue per recipient."""
        if self.total_recipients == 0:
            return 0
        return round(float(self.revenue) / self.total_recipients, 2)

    def get_tracking_url(self):
        """Generate a trackable URL with UTM parameters."""
        if not self.landing_url:
            return ""

        from urllib.parse import urlencode, urlparse, urlunparse, parse_qs

        parsed = urlparse(self.landing_url)
        params = parse_qs(parsed.query)

        # Add UTM parameters if specified
        if self.utm_source:
            params["utm_source"] = [self.utm_source]
        if self.utm_medium:
            params["utm_medium"] = [self.utm_medium]
        if self.utm_campaign:
            params["utm_campaign"] = [self.utm_campaign]
        if self.utm_content:
            params["utm_content"] = [self.utm_content]

        # Add variant for A/B testing
        if self.variant_name:
            params["variant"] = [self.variant_name]

        # Add promo code if there's a linked discount
        if self.discount and self.discount.code:
            params["code"] = [self.discount.code]

        # Rebuild URL with parameters
        query_string = urlencode(params, doseq=True)
        return urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params, query_string, parsed.fragment)
        )

    def get_tags_list(self):
        """Get list of test tags."""
        if not self.test_tags:
            return []
        return [tag.strip() for tag in self.test_tags.split(",") if tag.strip()]

    def get_content(self):
        """Get the message content (from template or custom)."""
        if self.custom_content:
            return self.custom_subject, self.custom_content

        if self.message_type == "email" and self.email_template:
            return self.email_template.subject, self.email_template.html_body
        elif self.message_type == "sms" and self.sms_template:
            return None, self.sms_template.message_body

        return None, ""

    def calculate_send_time(self, base_time=None):
        """Calculate when this message should be sent based on trigger type."""
        if self.trigger_type == "immediate":
            return timezone.now()
        elif self.trigger_type == "delay":
            if base_time is None:
                base_time = timezone.now()
            from datetime import timedelta

            return base_time + timedelta(days=self.delay_days, hours=self.delay_hours)
        elif self.trigger_type == "specific_date":
            return self.scheduled_date

        return timezone.now()
