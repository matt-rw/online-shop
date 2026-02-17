from django.db import models


class ReturnStatus(models.TextChoices):
    REQUESTED = "REQUESTED", "Requested"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    AWAITING_SHIPMENT = "AWAITING_SHIPMENT", "Awaiting Shipment"
    IN_TRANSIT = "IN_TRANSIT", "In Transit"
    RECEIVED = "RECEIVED", "Received"
    REFUNDED = "REFUNDED", "Refunded"


class ReturnReason(models.TextChoices):
    WRONG_SIZE = "WRONG_SIZE", "Wrong size"
    WRONG_ITEM = "WRONG_ITEM", "Wrong item received"
    DEFECTIVE = "DEFECTIVE", "Defective/damaged"
    NOT_AS_DESCRIBED = "NOT_AS_DESCRIBED", "Not as described"
    CHANGED_MIND = "CHANGED_MIND", "Changed mind"
    OTHER = "OTHER", "Other"


class Return(models.Model):
    order = models.ForeignKey(
        "shop.Order", on_delete=models.CASCADE, related_name="returns"
    )
    status = models.CharField(
        max_length=20, choices=ReturnStatus.choices, default=ReturnStatus.REQUESTED
    )
    reason = models.CharField(max_length=30, choices=ReturnReason.choices)
    customer_notes = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)

    # Return shipping
    tracking_number = models.CharField(max_length=100, blank=True)
    carrier = models.CharField(max_length=50, blank=True)
    return_label_url = models.URLField(blank=True)

    # Refund tracking
    refund_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    stripe_refund_id = models.CharField(max_length=100, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Return #{self.id} - Order #{self.order_id}"

    @property
    def total_refund_amount(self):
        """Calculate total refund amount from items"""
        return sum(item.refund_amount for item in self.items.all())

    @property
    def all_items_received(self):
        """Check if all items have been marked as received"""
        return self.items.exists() and all(item.received for item in self.items.all())


class ReturnItem(models.Model):
    return_request = models.ForeignKey(
        Return, on_delete=models.CASCADE, related_name="items"
    )
    order_item = models.ForeignKey("shop.OrderItem", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2)
    received = models.BooleanField(default=False)
    condition_notes = models.TextField(blank=True)

    def __str__(self):
        return f"ReturnItem #{self.id} - {self.order_item.sku} x{self.quantity}"
