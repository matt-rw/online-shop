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
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    def geocode(self):
        """Geocode this address using Nominatim and save coordinates."""
        from shop.utils.geocoding import geocode_address
        coords = geocode_address(self.city, self.region, self.postal_code, self.country)
        if coords:
            self.latitude, self.longitude = coords
            self.save(update_fields=['latitude', 'longitude'])
        return coords


class OrderTag(models.Model):
    """Customizable tags for categorizing orders (e.g., Influencer, Wholesale, Sample)."""
    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default="#6366f1", help_text="Hex color code")
    icon = models.CharField(max_length=50, blank=True, help_text="FontAwesome icon name (e.g., fa-star)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class OrderStatus(models.TextChoices):
    CREATED = "CREATED", "Created"
    AWAITING_PAYMENT = "AWAITING_PAYMENT", "Awaiting payment"
    PAID = "PAID", "Paid"
    FAILED = "FAILED", "Failed"
    CANCELED = "CANCELED", "Canceled"
    SHIPPED = "SHIPPED", "Shipped"
    FULFILLED = "FULFILLED", "Fulfilled"
    RETURN_REQUESTED = "RETURN_REQUESTED", "Return requested"
    REFUNDED = "REFUNDED", "Refunded"


class Order(models.Model):
    order_number = models.CharField(
        max_length=20, unique=True, blank=True,
        help_text="Professional order number (e.g., BP-10001)"
    )
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    customer_name = models.CharField(max_length=255, blank=True, help_text="Customer name (for manual orders)")
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True, help_text="Customer phone number")
    status = models.CharField(
        max_length=20, choices=OrderStatus.choices, default=OrderStatus.CREATED
    )

    def save(self, *args, **kwargs):
        if not self.order_number:
            # First save to get the ID if this is a new order
            if not self.pk:
                super().save(*args, **kwargs)
                args = ()  # Clear args after first save
                kwargs = {}
            # Generate order number based on actual ID: BP-10001, BP-10002, etc.
            self.order_number = f"BP-{10000 + self.pk}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.order_number or f"Order #{self.id}"

    shipping_address = models.ForeignKey(
        Address, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"  # Required?
    )
    billing_address = models.ForeignKey(
        Address, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"  # Required?
    )

    # Snapshotted money fields
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Discount amount applied")
    discount_code = models.CharField(max_length=50, blank=True, help_text="Discount/promo code used")
    free_shipping_code = models.CharField(max_length=50, blank=True, help_text="Free shipping code if applied")
    shipping = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    stripe_checkout_id = models.CharField(max_length=255, blank=True, db_index=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, db_index=True)

    # Test order flag
    is_test = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Test orders created via Test Center"
    )

    # Exclude from stats (for personal orders, samples, etc.)
    exclude_from_stats = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Exclude this order from revenue/profit calculations"
    )

    # Custom tags for categorizing orders
    tags = models.ManyToManyField(OrderTag, blank=True, related_name="orders")

    # Shipping label tracking
    tracking_number = models.CharField(max_length=255, blank=True)
    carrier = models.CharField(max_length=100, blank=True)  # e.g., USPS, UPS, FedEx
    label_url = models.URLField(blank=True)  # URL to download shipping label
    label_cost = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Actual cost paid for shipping label"
    )

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
