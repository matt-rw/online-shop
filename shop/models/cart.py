from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models
from wagtail.snippets.models import register_snippet

User = get_user_model()


# CARTS #
@register_snippet
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
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )
    session_key = models.CharField(max_length=255, db_index=True, null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        related_name='items',
        on_delete=models.CASCADE  # delete cart item if the cart is deleted
    )
    variant = models.ForeignKey(
        'shop.ProductVariant',
        on_delete=models.PROTECT  # keep cart item even if variant is deleted
    )
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)]
    )


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
    CREATED = 'CREATED', 'Created'
    AWAITING_PAYMENT = 'AWAITING_PAYMENT', 'Awaiting payment'
    PAID = 'PAID', 'Paid'
    FAILED = 'FAILED', 'Failed'
    CANCELED = 'CANCELED', 'Canceled'
    SHIPPED = 'SHIPPED', 'Shipped'
    FULFILLED = 'FULFILLED', 'Fulfilled'


class Order(models.Model):
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )
    email = models.EmailField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.CREATED
    )

    shipping_address = models.ForeignKey(
        Address,
        null=True,  # Required?
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+'
    )
    billing_address = models.ForeignKey(
        Address,
        null=True,  # Required?
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+'
    )

    # Snapshotted money fields
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    stripe_checkout_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True
    )
    stripe_payment_intent_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        related_name='items',
        on_delete=models.CASCADE
    )
    variant = models.ForeignKey(
        'shop.ProductVariant',
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )
    sku = models.CharField(max_length=50)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    line_total = models.DecimalField(max_digits=10, decimal_places=2)
