from django.contrib.auth.models import User
from django.db import models


class StockAdjustment(models.Model):
    """Records every stock change for audit trail and accountability."""
    ADJUSTMENT_TYPES = [
        ("count_correction", "Count Correction"),
        ("damaged", "Damaged"),
        ("sample", "Sample / Giveaway"),
        ("gift", "Gift"),
        ("return_received", "Return Received"),
        ("theft", "Theft / Loss"),
        ("shipment_received", "Shipment Received"),
        ("order_sold", "Order Sold"),
        ("manual", "Manual Adjustment"),
        ("other", "Other"),
    ]

    variant = models.ForeignKey(
        "shop.ProductVariant", on_delete=models.CASCADE, related_name="stock_adjustments"
    )
    adjustment_type = models.CharField(max_length=30, choices=ADJUSTMENT_TYPES, default="manual")
    previous_quantity = models.IntegerField()
    new_quantity = models.IntegerField()
    difference = models.IntegerField()
    reason = models.TextField(blank=True)
    adjusted_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["variant", "-created_at"], name="stockadj_variant_idx"),
            models.Index(fields=["-created_at"], name="stockadj_date_idx"),
        ]

    def __str__(self):
        return f"{self.variant} {self.difference:+d} ({self.get_adjustment_type_display()})"


class StockCount(models.Model):
    """A physical inventory count session."""
    STATUS_CHOICES = [
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
    ]

    name = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="in_progress")
    counted_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def total_items(self):
        return self.items.count()

    @property
    def discrepancy_count(self):
        return self.items.exclude(difference=0).count()

    @property
    def total_difference(self):
        from django.db.models import Sum
        return self.items.aggregate(total=Sum("difference"))["total"] or 0


class StockCountItem(models.Model):
    """Individual variant count within a count session."""
    stock_count = models.ForeignKey(StockCount, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(
        "shop.ProductVariant", on_delete=models.CASCADE, related_name="count_items"
    )
    system_quantity = models.IntegerField(help_text="Stock quantity when count started")
    physical_quantity = models.IntegerField(null=True, blank=True, help_text="Actual counted quantity")
    difference = models.IntegerField(default=0)
    applied = models.BooleanField(default=False, help_text="Whether this correction was applied to stock")

    class Meta:
        unique_together = ["stock_count", "variant"]
        ordering = ["variant__product__name"]

    def __str__(self):
        return f"{self.variant}: system={self.system_quantity}, physical={self.physical_quantity}"
