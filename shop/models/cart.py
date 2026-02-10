from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models

User = get_user_model()


# CARTS #
class Cart(models.Model):
    """
    Fields:
        user: links a cart to a logged-in user
        session_key: identifies carts for anonymous users
        is_active: a live cart that has not completed an order yet
        created_at: when the cart was first created
        updated_at: when the cart was last updated;
            useful for expiring old carts
    """

    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    session_key = models.CharField(max_length=255, db_index=True, null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        related_name="items",
        on_delete=models.CASCADE,  # delete cart item if the cart is deleted
    )
    variant = models.ForeignKey(
        "shop.ProductVariant", on_delete=models.PROTECT  # keep cart item even if variant is deleted
    )
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        unique_together = ["cart", "variant"]


class BundleCartItem(models.Model):
    """Cart item for bundles with selected size."""

    cart = models.ForeignKey(
        Cart,
        related_name="bundle_items",
        on_delete=models.CASCADE,
    )
    bundle = models.ForeignKey(
        "shop.Bundle", on_delete=models.PROTECT
    )
    size = models.ForeignKey(
        "shop.Size", on_delete=models.PROTECT
    )
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        unique_together = ["cart", "bundle", "size"]


# ORDERS #
class Address(models.Model):
    full_name = models.CharField(max_length=120)
    line1 = models.CharField(max_length=200)
    line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    region = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=2)
    email = models.EmailField(blank=True)


class OrderStatus(models.TextChoices):
    CREATED = "CREATED", "Created"
    AWAITING_PAYMENT = "AWAITING_PAYMENT", "Awaiting payment"
    PAID = "PAID", "Paid"
    FAILED = "FAILED", "Failed"
    CANCELED = "CANCELED", "Canceled"
    SHIPPED = "SHIPPED", "Shipped"
    FULFILLED = "FULFILLED", "Fulfilled"


class Order(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    email = models.EmailField(blank=True)
    status = models.CharField(
        max_length=20, choices=OrderStatus.choices, default=OrderStatus.CREATED
    )

    shipping_address = models.ForeignKey(
        Address, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"  # Required?
    )
    billing_address = models.ForeignKey(
        Address, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"  # Required?
    )

    # Snapshotted money fields
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    stripe_checkout_id = models.CharField(max_length=255, blank=True, db_index=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, db_index=True)

    # Shipping label tracking
    tracking_number = models.CharField(max_length=255, blank=True)
    carrier = models.CharField(max_length=100, blank=True)  # e.g., USPS, UPS, FedEx
    label_url = models.URLField(blank=True)  # URL to download shipping label

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    variant = models.ForeignKey(
        "shop.ProductVariant", null=True, blank=True, on_delete=models.SET_NULL
    )
    shipment_item = models.ForeignKey(
        "shop.ShipmentItem",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="order_items",
        help_text="The shipment batch this item was allocated from",
    )
    sku = models.CharField(max_length=50)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    line_total = models.DecimalField(max_digits=10, decimal_places=2)
    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Cost per unit at time of sale (from shipment)",
    )

    @property
    def profit(self):
        """Calculate profit for this line item"""
        if self.unit_cost is not None:
            revenue = self.line_total
            cost = self.unit_cost * self.quantity
            return revenue - cost
        return None

    @property
    def profit_margin(self):
        """Calculate profit margin percentage"""
        if self.unit_cost is not None and self.line_total > 0:
            profit = self.profit
            return (profit / self.line_total) * 100 if profit else 0
        return None

    def allocate_from_shipments(self):
        """
        Allocate this order item to shipment batches using FIFO.
        Returns True if fully allocated, False if insufficient stock.
        """
        from shop.models import ShipmentItem

        if not self.variant:
            return False

        # Find delivered shipment items for this variant, ordered by date (FIFO)
        available_shipments = (
            ShipmentItem.objects.filter(
                variant=self.variant,
                shipment__status="delivered",
            )
            .select_related("shipment")
            .order_by("shipment__date_received", "shipment__created_at")
        )

        # Find first shipment with available stock
        for shipment_item in available_shipments:
            if shipment_item.available_quantity >= self.quantity:
                self.shipment_item = shipment_item
                self.unit_cost = shipment_item.unit_cost
                self.save(update_fields=["shipment_item", "unit_cost"])
                return True

        # If no single shipment has enough, use the oldest with any stock
        # (for simplicity, we allocate to one shipment - could split if needed)
        for shipment_item in available_shipments:
            if shipment_item.available_quantity > 0:
                self.shipment_item = shipment_item
                self.unit_cost = shipment_item.unit_cost
                self.save(update_fields=["shipment_item", "unit_cost"])
                return True

        return False
