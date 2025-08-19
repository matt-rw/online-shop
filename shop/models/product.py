from django.db import models
from wagtail.snippets.models import register_snippet


@register_snippet
class Product(models.Model):
    """
    A data model used in carts, orders, and Stripe.

    Admin updates prices via Django Admin or Wagtail Snippets.
    """
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)  # todo: help description?
    # sku = models.CharField(max_length=50, blank=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    # stock_quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


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


# GENDER?


@register_snippet
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
    # todo: add SKU? autogenerate?
    color = models.ForeignKey(Color, on_delete=models.PROTECT)
    size = models.ForeignKey(Size, on_delete=models.PROTECT)
    stock_quantity = models.PositiveIntegerField(default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2)  # base price
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['product', 'size', 'color']

    def __str__(self):
        return f'{self.product.name} - {self.size} - {self.color}'
