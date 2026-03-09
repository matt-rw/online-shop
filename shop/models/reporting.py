from django.db import models
from django.utils import timezone

import pytz


class ScheduledReport(models.Model):
    """
    A scheduled report that sends automated email/SMS reports with business metrics.
    """

    STATUS_CHOICES = [
        ("active", "Active"),
        ("paused", "Paused"),
        ("disabled", "Disabled"),
    ]

    FREQUENCY_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
    ]

    DELIVERY_METHOD_CHOICES = [
        ("email", "Email"),
        ("sms", "SMS"),
        ("both", "Both"),
    ]

    WEEKLY_DAY_CHOICES = [
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
        (6, "Sunday"),
    ]

    # Basic info
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    # Scheduling
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default="daily")
    send_time = models.TimeField(
        help_text="Time to send the report (in America/Chicago timezone)"
    )
    weekly_day = models.IntegerField(
        choices=WEEKLY_DAY_CHOICES,
        default=0,
        help_text="Day of week for weekly reports (0=Monday)"
    )

    # Delivery
    delivery_method = models.CharField(
        max_length=20,
        choices=DELIVERY_METHOD_CHOICES,
        default="email"
    )
    email_recipients = models.TextField(
        blank=True,
        help_text="Comma-separated email addresses"
    )
    sms_recipients = models.TextField(
        blank=True,
        help_text="Comma-separated phone numbers in E.164 format"
    )

    # Report content
    selected_metrics = models.JSONField(
        default=list,
        help_text="List of metric IDs to include in the report"
    )
    include_comparison = models.BooleanField(
        default=True,
        help_text="Include period-over-period comparison"
    )

    # Scheduling timestamps
    last_sent_at = models.DateTimeField(null=True, blank=True)
    next_scheduled_at = models.DateTimeField(null=True, blank=True)

    # Tracking counts
    total_sends = models.IntegerField(default=0)
    failed_sends = models.IntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()})"

    def get_email_recipients_list(self):
        """Get list of email addresses."""
        if not self.email_recipients:
            return []
        return [e.strip() for e in self.email_recipients.split(",") if e.strip()]

    def get_sms_recipients_list(self):
        """Get list of phone numbers."""
        if not self.sms_recipients:
            return []
        return [p.strip() for p in self.sms_recipients.split(",") if p.strip()]

    def calculate_next_send_time(self, from_time=None):
        """
        Calculate the next send time based on frequency and settings.
        All times are in America/Chicago timezone.

        Args:
            from_time: Starting point for calculation (defaults to now)

        Returns:
            datetime: The next scheduled send time (timezone-aware)
        """
        from datetime import timedelta

        chicago_tz = pytz.timezone("America/Chicago")

        if from_time is None:
            from_time = timezone.now()

        # Convert to Chicago time
        chicago_now = from_time.astimezone(chicago_tz)

        # Create target time for today
        target_time = chicago_tz.localize(
            chicago_now.replace(
                hour=self.send_time.hour,
                minute=self.send_time.minute,
                second=0,
                microsecond=0
            ).replace(tzinfo=None)
        )

        if self.frequency == "daily":
            # If target time has passed today, schedule for tomorrow
            if target_time <= chicago_now:
                target_time = target_time + timedelta(days=1)

        elif self.frequency == "weekly":
            # Find the next occurrence of the specified day
            current_weekday = chicago_now.weekday()
            target_weekday = self.weekly_day

            days_ahead = target_weekday - current_weekday
            if days_ahead < 0:
                days_ahead += 7
            elif days_ahead == 0:
                # Same day - check if time has passed
                if target_time <= chicago_now:
                    days_ahead = 7

            target_time = target_time + timedelta(days=days_ahead)

        return target_time

    def save(self, *args, **kwargs):
        # Calculate next_scheduled_at if not set and report is active
        if self.status == "active" and not self.next_scheduled_at:
            self.next_scheduled_at = self.calculate_next_send_time()
        super().save(*args, **kwargs)


class ScheduledReportLog(models.Model):
    """
    Log entry for each scheduled report send attempt.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("partial", "Partial"),
        ("failed", "Failed"),
    ]

    report = models.ForeignKey(
        ScheduledReport,
        on_delete=models.CASCADE,
        related_name="logs"
    )

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Delivery counts
    email_sent = models.IntegerField(default=0)
    email_failed = models.IntegerField(default=0)
    sms_sent = models.IntegerField(default=0)
    sms_failed = models.IntegerField(default=0)

    # Period information
    period_start = models.DateTimeField(null=True, blank=True)
    period_end = models.DateTimeField(null=True, blank=True)
    comparison_period_start = models.DateTimeField(null=True, blank=True)
    comparison_period_end = models.DateTimeField(null=True, blank=True)

    # Snapshot of metrics at send time
    report_data = models.JSONField(
        default=dict,
        help_text="Snapshot of all metrics at the time of sending"
    )

    # Error tracking
    error_message = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.report.name} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    @property
    def total_sent(self):
        """Total successful deliveries."""
        return self.email_sent + self.sms_sent

    @property
    def total_failed(self):
        """Total failed deliveries."""
        return self.email_failed + self.sms_failed
