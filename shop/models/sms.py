from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models


class SMSSubscription(models.Model):
    phone_regex = RegexValidator(
        regex=r"^\+?1?\d{9,15}$",
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.",
    )

    phone_number = models.CharField(validators=[phone_regex], max_length=17, unique=True)
    is_confirmed = models.BooleanField(default=False)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=50, default="site_form")

    # Track opt-in/opt-out status
    is_active = models.BooleanField(default=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "SMS Subscription"
        verbose_name_plural = "SMS Subscriptions"
        ordering = ["-subscribed_at"]
        indexes = [
            # Campaign targeting (active confirmed subscribers)
            models.Index(fields=["is_active", "is_confirmed"], name="sms_campaign_idx"),
            # Subscription date sorting
            models.Index(fields=["-subscribed_at"], name="sms_subscribed_idx"),
        ]

    def __str__(self):
        return self.phone_number


class SMSTemplate(models.Model):
    """
    Reusable SMS message templates with variable support.
    Variables can be used like: {first_name}, {code}, {link}, etc.
    """

    TEMPLATE_TYPES = [
        ("welcome", "Welcome Message"),
        ("confirmation", "Confirmation Code"),
        ("promotion", "Promotional Message"),
        ("reminder", "Reminder"),
        ("announcement", "Announcement"),
        ("custom", "Custom"),
    ]

    TRIGGER_TYPES = [
        ("manual", "Manual Only"),
        ("on_subscribe", "On New Subscription"),
        ("on_confirmation", "On Confirmation Request"),
        ("scheduled", "Scheduled Campaign"),
    ]

    name = models.CharField(max_length=100, unique=True)
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPES, default="custom")
    message_body = models.TextField(
        max_length=1600,  # SMS can be up to 1600 chars for concatenated messages
        help_text="Use {variable_name} for dynamic content. Example: 'Hi {first_name}, your code is {code}'",
    )

    # Automatic trigger configuration
    auto_trigger = models.CharField(
        max_length=20,
        choices=TRIGGER_TYPES,
        default="manual",
        help_text="When should this template be automatically sent?",
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    # Track usage
    times_used = models.IntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True, help_text="Last time this template was used")

    # Organizational fields
    tags = models.TextField(blank=True, help_text="Comma-separated tags for categorization")
    notes = models.TextField(blank=True, help_text="Internal notes about this template")

    class Meta:
        verbose_name = "SMS Template"
        verbose_name_plural = "SMS Templates"
        ordering = ["template_type", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"

    def render(self, **kwargs):
        """
        Render the template with provided variables.

        Args:
            **kwargs: Variables to substitute in the template

        Returns:
            str: Rendered message
        """
        message = self.message_body
        for key, value in kwargs.items():
            placeholder = "{" + key + "}"
            message = message.replace(placeholder, str(value))
        return message


class SMSCampaign(models.Model):
    """
    SMS marketing campaigns that can be scheduled and tracked.
    """

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("sending", "Sending"),
        ("sent", "Sent"),
        ("paused", "Paused"),
        ("cancelled", "Cancelled"),
    ]

    name = models.CharField(max_length=200)
    template = models.ForeignKey(SMSTemplate, on_delete=models.PROTECT, related_name="campaigns")

    # Targeting
    send_to_all_active = models.BooleanField(
        default=True, help_text="Send to all active subscribers"
    )

    # Scheduling
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    scheduled_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Tracking
    total_recipients = models.IntegerField(default=0)
    sent_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "SMS Campaign"
        verbose_name_plural = "SMS Campaigns"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"


class SMSLog(models.Model):
    """
    Log of all SMS messages sent for tracking and debugging.
    """

    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("sent", "Sent"),
        ("delivered", "Delivered"),
        ("failed", "Failed"),
        ("undelivered", "Undelivered"),
    ]

    subscription = models.ForeignKey(
        SMSSubscription, on_delete=models.SET_NULL, null=True, blank=True, related_name="sms_logs"
    )
    phone_number = models.CharField(max_length=17)
    message_body = models.TextField()

    campaign = models.ForeignKey(
        SMSCampaign, on_delete=models.SET_NULL, null=True, blank=True, related_name="logs"
    )
    template = models.ForeignKey(
        SMSTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name="logs"
    )
    quick_message = models.ForeignKey(
        "shop.QuickMessage", on_delete=models.SET_NULL, null=True, blank=True, related_name="sms_logs"
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="queued")
    twilio_sid = models.CharField(max_length=34, blank=True)  # Twilio message SID

    sent_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    error_message = models.TextField(blank=True)
    cost = models.DecimalField(max_digits=6, decimal_places=4, null=True, blank=True)

    class Meta:
        verbose_name = "SMS Log"
        verbose_name_plural = "SMS Logs"
        ordering = ["-sent_at"]

    def __str__(self):
        return f"SMS to {self.phone_number} - {self.status}"
