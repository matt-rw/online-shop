from django.conf import settings
from django.db import models


class BugReport(models.Model):
    """Bug reports submitted by admin users."""

    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    screenshot = models.ImageField(upload_to='bug_reports/', blank=True, null=True)
    page_url = models.CharField(max_length=500, blank=True, help_text="URL where the bug occurred")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='bug_reports'
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_bugs'
    )

    admin_notes = models.TextField(blank=True, help_text="Internal notes (not visible to reporter)")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_status_display()}] {self.title}"

    @property
    def status_color(self):
        """Return a color for the status badge."""
        colors = {
            'open': '#ef4444',      # red
            'in_progress': '#f59e0b',  # amber
            'resolved': '#10b981',   # green
            'closed': '#6b7280',     # gray
        }
        return colors.get(self.status, '#6b7280')

    @property
    def priority_color(self):
        """Return a color for the priority badge."""
        colors = {
            'low': '#6b7280',       # gray
            'medium': '#3b82f6',    # blue
            'high': '#f59e0b',      # amber
            'critical': '#ef4444',  # red
        }
        return colors.get(self.priority, '#6b7280')
