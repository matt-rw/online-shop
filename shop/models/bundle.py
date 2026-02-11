from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class Bundle(models.Model):
    """
    A bundle of products sold together at a fixed price.
    Customer selects a size and all component products use that size.
    Example: "Foundation Set" in size M = Foundation Tee (M) + Foundation Pants (M)
    """

    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, db_index=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, help_text="Fixed bundle price (optional if using component pricing)"
    )
    use_component_pricing = models.BooleanField(
        default=False, help_text="Use sum of component prices instead of fixed price"
    )
    images = models.JSONField(default=list, blank=True, help_text="Bundle images")
    show_includes = models.BooleanField(default=True, help_text="Show 'Includes' section with component products on bundle page")
    is_active = models.BooleanField(default=True, db_index=True)
    available_for_purchase = models.BooleanField(
        default=True, help_text="Whether this bundle can be purchased (uncheck for coming soon/preview)"
    )
    featured = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def component_total(self):
        """Total price if buying components individually (uses base_price)."""
        total = Decimal("0.00")
        for item in self.items.select_related("product"):
            total += item.product.base_price * item.quantity
        return total

    @property
    def effective_price(self):
        """The actual price to charge - either fixed price or component total."""
        if self.use_component_pricing:
            return self.component_total
        return self.price or Decimal("0.00")

    @property
    def savings(self):
        """How much customer saves with bundle."""
        if self.use_component_pricing:
            return Decimal("0.00")
        return self.component_total - (self.price or Decimal("0.00"))

    @property
    def savings_percent(self):
        """Percentage saved with bundle."""
        if self.use_component_pricing:
            return 0
        if self.component_total > 0 and self.price:
            return int((self.savings / self.component_total) * 100)
        return 0

    def get_available_sizes(self):
        """
        Get sizes that are available for ALL products in the bundle.
        Returns list of Size objects that have stock for every component.
        """
        from .product import Size

        if not self.items.exists():
            return []

        # Get first product's available sizes as starting point
        first_item = self.items.select_related("product").first()
        if not first_item:
            return []

        # Get sizes with stock for first product
        available_size_ids = set(
            first_item.product.variants.filter(
                is_active=True, stock_quantity__gte=first_item.quantity
            ).values_list("size_id", flat=True)
        )

        # Intersect with each other product's available sizes
        for item in self.items.select_related("product").all()[1:]:
            item_size_ids = set(
                item.product.variants.filter(
                    is_active=True, stock_quantity__gte=item.quantity
                ).values_list("size_id", flat=True)
            )
            available_size_ids &= item_size_ids

        # Return Size objects in order
        return Size.objects.filter(id__in=available_size_ids).order_by("id")

    def get_variants_for_size(self, size):
        """
        Get the ProductVariant for each component product in the given size.
        Returns list of (BundleItem, ProductVariant) tuples, or None if any unavailable.
        """
        result = []
        for item in self.items.select_related("product").all():
            variant = item.product.variants.filter(
                size=size, is_active=True, stock_quantity__gte=item.quantity
            ).first()
            if not variant:
                return None
            result.append((item, variant))
        return result

    def is_available_in_size(self, size):
        """Check if bundle is available in the given size."""
        return self.get_variants_for_size(size) is not None


class BundleItem(models.Model):
    """
    A product included in a bundle.
    The actual variant is determined by the size selected at purchase.
    """

    bundle = models.ForeignKey(Bundle, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(
        "shop.Product", on_delete=models.PROTECT, related_name="bundle_items"
    )
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "id"]
        unique_together = ["bundle", "product"]

    def __str__(self):
        return f"{self.bundle.name} - {self.product.name}"
