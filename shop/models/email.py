from django.contrib.auth.models import User
from django.db import models


class EmailSubscription(models.Model):
    email = models.EmailField(unique=True)
    is_confirmed = models.BooleanField(default=False)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=50, default="site_form")

    # Track opt-in/opt-out status
    is_active = models.BooleanField(default=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)

    # unsub_token = models.CharField(max_length=64, unique=True)

    class Meta:
        verbose_name = "Email Subscription"
        verbose_name_plural = "Email Subscriptions"
        ordering = ["-subscribed_at"]
        indexes = [
            # Campaign targeting (active confirmed subscribers)
            models.Index(fields=["is_active", "is_confirmed"], name="email_campaign_idx"),
            # Subscription date sorting
            models.Index(fields=["-subscribed_at"], name="email_subscribed_idx"),
        ]

    def __str__(self):
        return self.email


class EmailTemplate(models.Model):
    """
    Reusable email templates with variable support.
    Variables can be used like: {first_name}, {code}, {link}, etc.
    """

    TEMPLATE_TYPES = [
        ("welcome", "Welcome Message"),
        ("confirmation", "Confirmation Email"),
        ("promotion", "Promotional Email"),
        ("newsletter", "Newsletter"),
        ("announcement", "Announcement"),
        ("custom", "Custom"),
    ]

    TRIGGER_TYPES = [
        ("manual", "Manual Only"),
        ("on_subscribe", "On New Subscription"),
        ("on_confirmation", "On Confirmation Request"),
        ("scheduled", "Scheduled Campaign"),
    ]

    FOLDER_CHOICES = [
        ("general", "General"),
        ("marketing", "Marketing"),
        ("transactional", "Transactional"),
        ("seasonal", "Seasonal"),
        ("onboarding", "Onboarding"),
        ("notifications", "Notifications"),
    ]

    name = models.CharField(max_length=100, unique=True)
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPES, default="custom")
    folder = models.CharField(
        max_length=50,
        default="general",
        help_text="Organize templates into folders for better organization",
    )

    # Email content
    subject = models.CharField(
        max_length=200, help_text="Email subject line. Supports variables like {first_name}"
    )
    html_body = models.TextField(
        help_text="HTML email body. Use {variable_name} for dynamic content."
    )
    text_body = models.TextField(
        blank=True,
        help_text="Plain text version (optional, will be auto-generated from HTML if empty)",
    )

    # Visual editor design
    design_json = models.JSONField(
        null=True,
        blank=True,
        help_text="Visual email builder design data (JSON format from Unlayer)",
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
        verbose_name = "Email Template"
        verbose_name_plural = "Email Templates"
        ordering = ["template_type", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"

    def render(self, **kwargs):
        """
        Render the template with provided variables.

        Args:
            **kwargs: Variables to substitute in the template

        Returns:
            tuple: (rendered_subject, rendered_html_body, rendered_text_body)
        """
        subject = self.subject
        html_body = self.html_body
        text_body = self.text_body

        for key, value in kwargs.items():
            placeholder = "{" + key + "}"
            subject = subject.replace(placeholder, str(value))
            html_body = html_body.replace(placeholder, str(value))
            if text_body:
                text_body = text_body.replace(placeholder, str(value))

        return subject, html_body, text_body


class EmailCampaign(models.Model):
    """
    Email marketing campaigns that can be scheduled and tracked.
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
    template = models.ForeignKey(EmailTemplate, on_delete=models.PROTECT, related_name="campaigns")

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
        verbose_name = "Email Campaign"
        verbose_name_plural = "Email Campaigns"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"


class EmailLog(models.Model):
    """
    Log of all emails sent for tracking and debugging.
    """

    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("sent", "Sent"),
        ("delivered", "Delivered"),
        ("failed", "Failed"),
        ("bounced", "Bounced"),
    ]

    subscription = models.ForeignKey(
        EmailSubscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_logs",
    )
    email_address = models.EmailField()
    subject = models.CharField(max_length=200)
    html_body = models.TextField()
    text_body = models.TextField(blank=True)

    campaign = models.ForeignKey(
        EmailCampaign, on_delete=models.SET_NULL, null=True, blank=True, related_name="logs"
    )
    template = models.ForeignKey(
        EmailTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name="logs"
    )
    quick_message = models.ForeignKey(
        "shop.QuickMessage", on_delete=models.SET_NULL, null=True, blank=True, related_name="email_logs"
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="queued")

    sent_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    error_message = models.TextField(blank=True)

    class Meta:
        verbose_name = "Email Log"
        verbose_name_plural = "Email Logs"
        ordering = ["-sent_at"]

    def __str__(self):
        return f"Email to {self.email_address} - {self.status}"


class TemplateFolder(models.Model):
    """
    Custom folders for organizing email templates.
    """
    name = models.CharField(max_length=50, unique=True)
    display_name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Template Folder"
        verbose_name_plural = "Template Folders"
        ordering = ["display_name"]

    def __str__(self):
        return self.display_name
