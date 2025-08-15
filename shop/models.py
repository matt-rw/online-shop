from django.db import models


class Product(models.Model):
    """
    A data model used in carts, orders, and Stripe.

    Admin updates prices via Django Admin or Wagtail Snippets.
    """
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    # sku = models.CharField(max_length=50, blank=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    # stock_quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class CartItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)


class Size(models.Model):
    # VARIABLE?
    name = models.CharField(
        max_length=10,
        choices=[
            # choices = [(internal_value, human_readable_label)]
            ('XS', 'XS'), ('S', 'S'), ('M', 'M'), ('L', 'L'), ('XL', 'XL')
        ]
    )


class Color(models.Model):
    name = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.name


# GENDER?


class ProductVariant(models.Model):
    """
    An instance or configuration of a product, not a type of product.

    Each variant contains attributes that can change (stock, size, color, SKU).
    """
    product = models.ForeignKey(
        Product,
        related_name='variants',
        on_delete=models.CASCADE
        )
    color = models.ForeignKey(Color, on_delete=models.PROTECT)
    size = models.ForeignKey(Size, on_delete=models.PROTECT)
    stock_quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['product', 'size', 'color']

    def __str__(self):
        return f'{self.product.name} - {self.size} - {self.color}'
