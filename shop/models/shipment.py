from django.db import models
from wagtail.snippets.models import register_snippet


@register_snippet
class Shipment(models.Model):
    """Incoming shipment tracking for inventory restocking"""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in-transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('delayed', 'Delayed'),
    ]

    tracking_number = models.CharField(max_length=100, unique=True)
    supplier = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    expected_date = models.DateField()
    actual_delivery_date = models.DateField(null=True, blank=True)
    item_count = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-expected_date']

    def __str__(self):
        return f"{self.tracking_number} - {self.supplier}"

    panels = [
        # For Wagtail admin if needed
    ]
