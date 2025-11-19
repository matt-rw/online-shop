from django.db import models
from wagtail.snippets.models import register_snippet


@register_snippet
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
    uses_size = models.BooleanField(default=False, help_text='Does this category use size variants?')
    uses_color = models.BooleanField(default=False, help_text='Does this category use color variants?')
    uses_material = models.BooleanField(default=False, help_text='Does this category use material variants?')

    # Custom variant attributes (stored as JSON)
    # Format: [{"name": "Storage", "type": "select", "options": ["64GB", "128GB", "256GB"]}, ...]
    custom_attributes = models.JSONField(
        default=list,
        blank=True,
        help_text='Custom variant attributes specific to this category'
    )

    # Common custom fields for this category
    # Format: [{"name": "Weight", "unit": "oz", "required": false}, ...]
    common_fields = models.JSONField(
        default=list,
        blank=True,
        help_text='Common custom fields that products in this category typically have'
    )

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


@register_snippet
class Product(models.Model):
    """
    A core product type (e.g., "Classic T-Shirt").

    This represents a single product concept, regardless of size/color variants.
    For example: "Classic T-Shirt" is ONE product, even if it comes in
    30 different size/color combinations.
    """
    name = models.CharField(max_length=255, help_text='Product name (e.g., "Classic T-Shirt")')
    slug = models.SlugField(unique=True, db_index=True)
    description = models.TextField(blank=True, help_text='Product description and details')

    # Legacy category field (deprecated - use category_obj instead)
    category_legacy = models.CharField(
        max_length=100,
        blank=True,
        help_text='DEPRECATED: Old category field',
        db_column='category',  # Keep same database column name
        db_index=True
    )

    # New category system
    category_obj = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='products',
        help_text='Product category - determines available variant attributes'
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
            self.category_legacy = str(value) if value else ''
    # Images will be handled by a separate ProductImage model for better management
    # image_urls field removed in favor of file uploads
    base_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Starting/base price for this product'
    )
    is_active = models.BooleanField(default=True, db_index=True)
    featured = models.BooleanField(
        default=False,
        help_text='Feature this product on homepage',
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def total_stock(self):
        """Total stock across all variants"""
        from django.db.models import Sum
        return self.variants.aggregate(total=Sum('stock_quantity'))['total'] or 0

    @property
    def variant_count(self):
        """Number of variants (size/color combinations)"""
        return self.variants.count()


@register_snippet
class Size(models.Model):
    code = models.CharField(max_length=32, unique=True)
    # choices=[
    #   choices = [(internal_value, human_readable_label)]
    #   ('XS', 'XS'), ('S', 'S'), ('M', 'M'), ('L', 'L'), ('XL', 'XL')
    # ]
    label = models.CharField(max_length=64, blank=True)

    def __str__(self):
        return self.label or self.code


@register_snippet
class Color(models.Model):
    name = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.name


@register_snippet
class Material(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


# GENDER?


@register_snippet
class ProductVariant(models.Model):
    """
    A specific variant of a product with unique attribute combinations.

    The available attributes are determined by the product's category.
    For example, an Apparel product might use Size + Color + Material,
    while an Electronics product might use Screen Size + Color + Storage.
    """
    product = models.ForeignKey(
        Product,
        related_name='variants',
        on_delete=models.CASCADE
    )
    sku = models.CharField(
        max_length=50,
        blank=True,
        unique=True,
        null=True,
        help_text='Stock Keeping Unit - auto-generated if blank'
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
        help_text='Dynamic variant attributes based on category configuration'
    )

    stock_quantity = models.PositiveIntegerField(default=0)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Price for this specific variant'
    )
    is_active = models.BooleanField(default=True, db_index=True)

    # Images and custom data
    images = models.JSONField(default=list, blank=True, help_text='List of image URLs')
    custom_fields = models.JSONField(default=dict, blank=True, help_text='Custom key-value data')

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

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
            parts.append(f'{key}: {value}')

        return ' - '.join(parts)

    def save(self, *args, **kwargs):
        # Auto-generate SKU if not provided
        if not self.sku:
            parts = [self.product.slug[:15].upper().replace('-', '')]

            # Add standard attributes
            if self.size:
                parts.append(self.size.code.upper())
            if self.color:
                parts.append(self.color.name[:8].upper().replace(' ', ''))
            if self.material:
                parts.append(self.material.name[:8].upper().replace(' ', ''))

            # Add dynamic attributes
            for key, value in self.variant_attributes.items():
                parts.append(str(value)[:8].upper().replace(' ', ''))

            self.sku = '-'.join(parts)
        super().save(*args, **kwargs)


class Discount(models.Model):
    """
    Discount codes and automatic deals.
    """
    DISCOUNT_TYPES = [
        ('percentage', 'Percentage Off'),
        ('fixed', 'Fixed Amount Off'),
        ('bogo', 'Buy One Get One'),
        ('free_shipping', 'Free Shipping'),
    ]

    name = models.CharField(max_length=200, help_text='Internal name for this discount')
    code = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        help_text='Discount code (leave blank for auto-apply)'
    )
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPES, default='percentage')
    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Percentage (e.g., 20 for 20%) or fixed amount (e.g., 10.00 for $10 off)'
    )

    # Restrictions
    min_purchase_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Minimum purchase amount to qualify'
    )
    max_uses = models.IntegerField(
        null=True,
        blank=True,
        help_text='Maximum number of times this discount can be used (blank = unlimited)'
    )
    times_used = models.IntegerField(default=0)

    # Validity
    valid_from = models.DateTimeField(help_text='Discount becomes active at this time')
    valid_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Discount expires at this time (blank = no expiration)'
    )
    is_active = models.BooleanField(default=True, db_index=True)

    # Product targeting
    applies_to_all = models.BooleanField(
        default=True,
        help_text='Apply to all products or specific products only'
    )
    products = models.ManyToManyField(
        Product,
        blank=True,
        related_name='discounts',
        help_text='Specific products this discount applies to (if not applying to all)'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Discount'
        verbose_name_plural = 'Discounts'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

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
