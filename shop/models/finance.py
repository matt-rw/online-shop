from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class ExpenseCategory(models.Model):
    """Categories for expenses (Shipping, Marketing, Photography, etc.)"""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default="#667eea", help_text="Hex color for charts")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Expense Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Expense(models.Model):
    """Track all business expenses"""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("cancelled", "Cancelled"),
    ]

    PAYMENT_METHOD_CHOICES = [
        ("cash", "Cash"),
        ("credit_card", "Credit Card"),
        ("debit_card", "Debit Card"),
        ("bank_transfer", "Bank Transfer"),
        ("paypal", "PayPal"),
        ("stripe", "Stripe"),
        ("check", "Check"),
        ("other", "Other"),
    ]

    # Basic information
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name="expenses")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255)
    notes = models.TextField(blank=True)

    # Date and status
    date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Payment details
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True)
    vendor = models.CharField(max_length=255, blank=True, help_text="Supplier or vendor name")

    # Optional: Link to order for shipping costs
    related_order = models.ForeignKey(
        "Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
        help_text="Link shipping costs to specific orders"
    )

    # Receipt/proof
    receipt = models.FileField(upload_to="receipts/%Y/%m/", blank=True, null=True)

    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="expenses_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(fields=["-date"]),
            models.Index(fields=["category", "-date"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.category.name} - ${self.amount} - {self.date}"

    @property
    def is_paid(self):
        return self.status == "paid"

    @property
    def is_pending(self):
        return self.status == "pending"


class Revenue(models.Model):
    """Track revenue from orders and other sources"""

    SOURCE_CHOICES = [
        ("order", "Order"),
        ("wholesale", "Wholesale"),
        ("refund_received", "Refund Received"),
        ("other", "Other"),
    ]

    PAYMENT_METHOD_CHOICES = [
        ("stripe", "Stripe"),
        ("paypal", "PayPal"),
        ("cash", "Cash"),
        ("bank_transfer", "Bank Transfer"),
        ("other", "Other"),
    ]

    # Basic information
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="other")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255)
    notes = models.TextField(blank=True)

    # Date
    date = models.DateField(default=timezone.now)

    # Payment details
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True)

    # Optional: Link to order
    related_order = models.ForeignKey(
        "Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revenues",
        help_text="Link to order if this revenue is from an order"
    )

    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="revenues_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(fields=["-date"]),
            models.Index(fields=["source", "-date"]),
        ]

    def __str__(self):
        return f"{self.source} - ${self.amount} - {self.date}"
