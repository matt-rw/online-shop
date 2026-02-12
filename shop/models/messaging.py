from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class QuickMessage(models.Model):
    """
    Quick messages sent directly from the admin dashboard.
    Groups individual email/SMS logs for aggregate tracking.
    """

    MESSAGE_TYPES = [
        ("email", "Email"),
        ("sms", "SMS"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("sending", "Sending"),
        ("sent", "Sent"),
        ("partial", "Partially Sent"),
        ("failed", "Failed"),
    ]

    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES)

    # Content
    subject = models.CharField(
        max_length=200, blank=True, help_text="Subject line (for emails only)"
    )
    content = models.TextField(help_text="Message content")

    # Stats
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="sending")
    recipient_count = models.IntegerField(default=0)
    sent_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="quick_messages"
    )
    notes = models.TextField(blank=True, help_text="Internal notes")

    # Scheduling
    scheduled_for = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Schedule message to be sent at this time (leave empty to send immediately)",
    )

    class Meta:
        verbose_name = "Quick Message"
        verbose_name_plural = "Quick Messages"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"], name="quickmsg_created_idx"),
            models.Index(fields=["status"], name="quickmsg_status_idx"),
            models.Index(fields=["message_type", "-created_at"], name="quickmsg_type_idx"),
            # Index for scheduler query: status + scheduled_for
            models.Index(fields=["status", "scheduled_for"], name="quickmsg_scheduled_idx"),
        ]

    def __str__(self):
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"{self.get_message_type_display()} - {preview}"

    @property
    def success_rate(self):
        """Calculate the percentage of successfully sent messages."""
        if self.recipient_count == 0:
            return 0
        return round((self.sent_count / self.recipient_count) * 100, 1)
