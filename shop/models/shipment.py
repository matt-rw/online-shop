from django.db import models
from django.db.models import Sum



class Shipment(models.Model):
    """Incoming shipment tracking for inventory restocking"""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in-transit", "In Transit"),
        ("delivered", "Delivered"),
        ("delayed", "Delayed"),
    ]

    name = models.CharField(max_length=200, blank=True, help_text="Friendly name for this shipment (e.g., 'Spring 2025 Restock')")
    tracking_number = models.CharField(max_length=100, unique=True)
    supplier = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Dates
    date_shipped = models.DateField(null=True, blank=True, help_text="Date shipment left supplier")
    expected_date = models.DateField(help_text="Expected delivery date")
    date_received = models.DateField(null=True, blank=True, help_text="Actual date received")

    # Costs
    manufacturing_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, help_text="Total manufacturing/production cost"
    )
    shipping_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, help_text="Shipping and freight cost"
    )
    customs_duty = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, help_text="Customs duty and import fees"
    )
    other_fees = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Other fees (insurance, handling, etc.)",
    )

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-expected_date"]

    def __str__(self):
        if self.name:
            return self.name
        return f"{self.tracking_number} - {self.supplier}"

    @property
    def item_count(self):
        """Total items across all variants in this shipment"""
        return self.items.aggregate(total=Sum("quantity"))["total"] or 0

    @property
    def variant_count(self):
        """Number of different variants in this shipment"""
        return self.items.count()

    @property
    def total_cost(self):
        """Total cost including all fees"""
        return self.manufacturing_cost + self.shipping_cost + self.customs_duty + self.other_fees

    @property
    def items_subtotal(self):
        """Sum of all item costs (quantity * unit_cost)"""
        return (
            self.items.aggregate(total=Sum(models.F("quantity") * models.F("unit_cost")))["total"]
            or 0
        )

    panels = [
        # For Wagtail admin if needed
    ]


class ShipmentItem(models.Model):
    """Individual variant quantities within a shipment"""

    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(
        "ProductVariant", on_delete=models.CASCADE, related_name="shipment_items"
    )
    quantity = models.PositiveIntegerField(default=0, help_text="Quantity ordered")
    received_quantity = models.PositiveIntegerField(
        default=0, help_text="Actual quantity received (may differ from ordered)"
    )
    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Cost per unit for this variant in this shipment",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["shipment", "variant"]
        ordering = ["shipment", "variant"]

    def __str__(self):
        return f"{self.shipment.tracking_number} - {self.variant.sku} ({self.quantity} units)"

    @property
    def total_cost(self):
        """Total cost for this line item"""
        return self.quantity * self.unit_cost
