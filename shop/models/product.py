from django.db import models


class Category(models.Model):
    """
    Product category that defines what variant attributes are relevant.
    For example: "Apparel" category would use Size, Color, Material
    while "Electronics" might use Screen Size, Color, Storage Capacity
    """

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)

    # Define which attribute types this category uses
    uses_size = models.BooleanField(
        default=False, help_text="Does this category use size variants?"
    )
    uses_color = models.BooleanField(
        default=False, help_text="Does this category use color variants?"
    )
    uses_material = models.BooleanField(
        default=False, help_text="Does this category use material variants?"
    )

    # Custom variant attributes (stored as JSON)
    # Format: [{"name": "Storage", "type": "select", "options": ["64GB", "128GB", "256GB"]}, ...]
    custom_attributes = models.JSONField(
        default=list, blank=True, help_text="Custom variant attributes specific to this category"
    )

    # Common custom fields for this category
    # Format: [{"name": "Weight", "unit": "oz", "required": false}, ...]
    common_fields = models.JSONField(
        default=list,
        blank=True,
        help_text="Common custom fields that products in this category typically have",
    )

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    """
    A core product type (e.g., "Classic T-Shirt").

    This represents a single product concept, regardless of size/color variants.
    For example: "Classic T-Shirt" is ONE product, even if it comes in
    30 different size/color combinations.
    """

    name = models.CharField(max_length=255, help_text='Product name (e.g., "Classic T-Shirt")')
    slug = models.SlugField(unique=True, db_index=True)
    description = models.TextField(blank=True, help_text="Product description and details")

    # Legacy category field (deprecated - use category_obj instead)
    category_legacy = models.CharField(
        max_length=100,
        blank=True,
        help_text="DEPRECATED: Old category field",
        db_column="category",  # Keep same database column name
        db_index=True,
    )

    # New category system
    category_obj = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="products",
        help_text="Product category - determines available variant attributes",
    )

    @property
    def category(self):
        """Return category_obj if set, otherwise return legacy string"""
        return self.category_obj if self.category_obj else self.category_legacy

    @category.setter
    def category(self, value):
        """Set category - accepts either Category instance or string"""
        if isinstance(value, Category):
            self.category_obj = value
        else:
            self.category_legacy = str(value) if value else ""

    # Product-level images shared across all variants
    images = models.JSONField(
        default=list, blank=True, help_text="Shared product images (used for all variants)"
    )

    base_price = models.DecimalField(
        max_digits=10, decimal_places=2, help_text="Starting/base price for this product"
    )
    is_active = models.BooleanField(default=True, db_index=True)
    available_for_purchase = models.BooleanField(
        default=True, help_text="If False, product is visible but shows 'Not Available' instead of Add to Cart"
    )
    featured = models.BooleanField(
        default=False, help_text="Feature this product on homepage", db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            # Sorting products by creation date (newest first)
            models.Index(fields=["-created_at"], name="product_created_idx"),
            # Filtering active products (most common query)
            models.Index(fields=["is_active", "-created_at"], name="product_active_idx"),
            # Featured products query
            models.Index(fields=["featured", "is_active"], name="product_featured_idx"),
        ]

    def __str__(self):
        return self.name

    @property
    def total_stock(self):
        """Total stock across all variants"""
        from django.db.models import Sum

        return self.variants.aggregate(total=Sum("stock_quantity"))["total"] or 0

    @property
    def variant_count(self):
        """Number of variants (size/color combinations)"""
        return self.variants.count()


class Size(models.Model):
    code = models.CharField(max_length=32, unique=True)
    # choices=[
    #   choices = [(internal_value, human_readable_label)]
    #   ('XS', 'XS'), ('S', 'S'), ('M', 'M'), ('L', 'L'), ('XL', 'XL')
    # ]
    label = models.CharField(max_length=64, blank=True)

    def __str__(self):
        return self.label or self.code


class Color(models.Model):
    name = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.name


class Material(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class CustomAttribute(models.Model):
    """
    A custom attribute type that can be used for product variants.
    Examples: Waist, Inseam, Lens Color, Screen Size, etc.
    """
    name = models.CharField(max_length=100, unique=True, help_text="Attribute name (e.g., Waist, Inseam)")
    slug = models.SlugField(unique=True, help_text="URL-friendly identifier")
    description = models.TextField(blank=True, help_text="Optional description of this attribute")
    is_active = models.BooleanField(default=True, help_text="Whether this attribute is available for use")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Custom Attribute"
        verbose_name_plural = "Custom Attributes"

    def __str__(self):
        return self.name


class CustomAttributeValue(models.Model):
    """
    A value for a custom attribute.
    Examples: For "Waist" attribute: 28, 30, 32, 34, etc.
    """
    attribute = models.ForeignKey(
        CustomAttribute,
        on_delete=models.CASCADE,
        related_name="values",
        help_text="The attribute this value belongs to"
    )
    value = models.CharField(max_length=100, help_text="The attribute value (e.g., 28, 30, 32)")
    display_order = models.PositiveIntegerField(default=0, help_text="Order in which to display this value")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["attribute", "display_order", "value"]
        unique_together = ["attribute", "value"]
        verbose_name = "Custom Attribute Value"
        verbose_name_plural = "Custom Attribute Values"

    def __str__(self):
        return f"{self.attribute.name}: {self.value}"


# GENDER?


class ProductVariant(models.Model):
    """
    A specific variant of a product with unique attribute combinations.

    The available attributes are determined by the product's category.
    For example, an Apparel product might use Size + Color + Material,
    while an Electronics product might use Screen Size + Color + Storage.
    """

    product = models.ForeignKey(Product, related_name="variants", on_delete=models.CASCADE)
    sku = models.CharField(
        max_length=50,
        blank=True,
        unique=True,
        null=True,
        help_text="Stock Keeping Unit - auto-generated if blank",
    )

    # Optional standard attributes (only used if category specifies)
    size = models.ForeignKey(Size, on_delete=models.PROTECT, null=True, blank=True)
    color = models.ForeignKey(Color, on_delete=models.PROTECT, null=True, blank=True)
    material = models.ForeignKey(Material, on_delete=models.PROTECT, null=True, blank=True)

    # Dynamic variant attributes (category-specific)
    # Format: {"Storage": "256GB", "Processor": "M2", ...}
    variant_attributes = models.JSONField(
        default=dict,
        blank=True,
        help_text="Dynamic variant attributes based on category configuration",
    )

    stock_quantity = models.PositiveIntegerField(default=0)
    price = models.DecimalField(
        max_digits=10, decimal_places=2, help_text="Price for this specific variant"
    )
    is_active = models.BooleanField(default=True, db_index=True)

    # Images and custom data
    images = models.JSONField(default=list, blank=True, help_text="List of image URLs")
    custom_fields = models.JSONField(default=dict, blank=True, help_text="Custom key-value data")

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            # Variant lookup by product and attributes (most common)
            models.Index(fields=["product", "size", "color"], name="variant_lookup_idx"),
            # Active variants with stock
            models.Index(fields=["is_active", "stock_quantity"], name="variant_stock_idx"),
            # SKU lookup
            models.Index(fields=["sku"], name="variant_sku_idx"),
        ]

    def __str__(self):
        parts = [self.product.name]

        # Add standard attributes if present
        if self.size:
            parts.append(str(self.size))
        if self.color:
            parts.append(str(self.color))
        if self.material:
            parts.append(str(self.material))

        # Add dynamic attributes
        for key, value in self.variant_attributes.items():
            parts.append(f"{key}: {value}")

        return " - ".join(parts)

    def save(self, *args, **kwargs):
        # Auto-generate SKU if not provided
        if not self.sku:
            parts = [self.product.slug[:15].upper().replace("-", "")]

            # Add standard attributes
            if self.size:
                parts.append(self.size.code.upper())
            if self.color:
                parts.append(self.color.name[:8].upper().replace(" ", ""))
            if self.material:
                parts.append(self.material.name[:8].upper().replace(" ", ""))

            # Add dynamic attributes
            for key, value in self.variant_attributes.items():
                parts.append(str(value)[:8].upper().replace(" ", ""))

            self.sku = "-".join(parts)
        super().save(*args, **kwargs)


class Discount(models.Model):
    """
    Discount codes and automatic deals.
    """

    DISCOUNT_TYPES = [
        ("percentage", "Percentage Off"),
        ("fixed", "Fixed Amount Off"),
        ("bogo", "Buy One Get One"),
        ("free_shipping", "Free Shipping"),
    ]

    name = models.CharField(max_length=200, help_text="Internal name for this discount")
    code = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        help_text="Discount code (leave blank for auto-apply)",
    )
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPES, default="percentage")
    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Percentage (e.g., 20 for 20%) or fixed amount (e.g., 10.00 for $10 off)",
    )

    # Restrictions
    min_purchase_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Minimum purchase amount to qualify",
    )
    max_uses = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of times this discount can be used (blank = unlimited)",
    )
    times_used = models.IntegerField(default=0)

    # Validity
    valid_from = models.DateTimeField(help_text="Discount becomes active at this time")
    valid_until = models.DateTimeField(
        null=True, blank=True, help_text="Discount expires at this time (blank = no expiration)"
    )
    is_active = models.BooleanField(default=True, db_index=True)

    # Product targeting
    applies_to_all = models.BooleanField(
        default=True, help_text="Apply to all products or specific products only"
    )
    products = models.ManyToManyField(
        Product,
        blank=True,
        related_name="discounts",
        help_text="Specific products this discount applies to (if not applying to all)",
    )

    # URL Tracking
    landing_url = models.URLField(
        blank=True,
        help_text="Landing page URL for this promo code (e.g., https://site.com/sale)",
    )
    utm_source = models.CharField(
        max_length=100, blank=True, help_text="UTM Source (e.g., instagram, facebook, email)"
    )
    utm_medium = models.CharField(
        max_length=100, blank=True, help_text="UTM Medium (e.g., social, cpc, email)"
    )
    utm_campaign = models.CharField(
        max_length=100, blank=True, help_text="UTM Campaign name (e.g., summer_sale_2025)"
    )

    # A/B Testing
    variant_name = models.CharField(
        max_length=50,
        blank=True,
        help_text="Variant identifier (e.g., 'A', 'B', '20%', '50%')",
    )
    test_tags = models.CharField(
        max_length=255,
        blank=True,
        help_text="Comma-separated tags for testing (e.g., 'percentage,newcustomer,holiday')",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Discount"
        verbose_name_plural = "Discounts"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def get_tracking_url(self):
        """Generate a trackable URL with UTM parameters and promo code."""
        if not self.landing_url:
            return ""

        from urllib.parse import urlencode, urlparse, urlunparse, parse_qs

        parsed = urlparse(self.landing_url)
        params = parse_qs(parsed.query)

        # Add UTM parameters if specified
        if self.utm_source:
            params["utm_source"] = [self.utm_source]
        if self.utm_medium:
            params["utm_medium"] = [self.utm_medium]
        if self.utm_campaign:
            params["utm_campaign"] = [self.utm_campaign]

        # Add variant for A/B testing
        if self.variant_name:
            params["variant"] = [self.variant_name]

        # Add promo code as a parameter
        if self.code:
            params["code"] = [self.code]

        # Rebuild URL with parameters
        query_string = urlencode(params, doseq=True)
        return urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params, query_string, parsed.fragment)
        )

    def get_tags_list(self):
        """Get list of test tags."""
        if not self.test_tags:
            return []
        return [tag.strip() for tag in self.test_tags.split(",") if tag.strip()]

    @property
    def conversion_rate(self):
        """Calculate conversion rate (uses / total tracked usage)."""
        # This will be more useful once we implement click tracking
        return 0

    @property
    def is_valid(self):
        """Check if discount is currently valid"""
        from django.utils import timezone

        now = timezone.now()

        if not self.is_active:
            return False

        if self.valid_from > now:
            return False

        if self.valid_until and self.valid_until < now:
            return False

        if self.max_uses and self.times_used >= self.max_uses:
            return False

        return True
