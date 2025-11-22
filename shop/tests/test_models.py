"""
Tests for shop models.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from shop.models import (
    Address,
    Cart,
    CartItem,
    Color,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    ProductVariant,
    Size,
)

from .test_helpers import create_test_user

User = get_user_model()


class ProductModelTestCase(TestCase):
    """Test cases for Product model."""

    def test_create_product(self):
        """Test creating a product."""
        product = Product.objects.create(
            name="Test T-Shirt", slug="test-tshirt", base_price=Decimal("29.99"), is_active=True
        )

        self.assertEqual(product.name, "Test T-Shirt")
        self.assertEqual(product.slug, "test-tshirt")
        self.assertEqual(product.base_price, Decimal("29.99"))
        self.assertTrue(product.is_active)

    def test_product_str(self):
        """Test Product string representation."""
        product = Product.objects.create(
            name="Test T-Shirt", slug="test-tshirt", base_price=Decimal("29.99")
        )

        self.assertEqual(str(product), "Test T-Shirt")


class ProductVariantModelTestCase(TestCase):
    """Test cases for ProductVariant model."""

    def setUp(self):
        """Set up test data."""
        self.product = Product.objects.create(
            name="Test T-Shirt", slug="test-tshirt", base_price=Decimal("29.99")
        )
        self.size = Size.objects.create(code="M", label="Medium")
        self.color = Color.objects.create(name="Black")

    def test_create_product_variant(self):
        """Test creating a product variant."""
        variant = ProductVariant.objects.create(
            product=self.product,
            size=self.size,
            color=self.color,
            stock_quantity=10,
            price=Decimal("29.99"),
            is_active=True,
        )

        self.assertEqual(variant.product, self.product)
        self.assertEqual(variant.size, self.size)
        self.assertEqual(variant.color, self.color)
        self.assertEqual(variant.stock_quantity, 10)

    def test_product_variant_str(self):
        """Test ProductVariant string representation."""
        variant = ProductVariant.objects.create(
            product=self.product,
            size=self.size,
            color=self.color,
            stock_quantity=10,
            price=Decimal("29.99"),
        )

        variant_str = str(variant)
        self.assertIn("Test T-Shirt", variant_str)
        self.assertIn("Medium", variant_str)
        self.assertIn("Black", variant_str)

    def test_product_variant_unique_together(self):
        """Test that product/size/color combination is unique."""
        ProductVariant.objects.create(
            product=self.product,
            size=self.size,
            color=self.color,
            stock_quantity=10,
            price=Decimal("29.99"),
        )

        # Creating duplicate should fail
        with self.assertRaises(Exception):
            ProductVariant.objects.create(
                product=self.product,
                size=self.size,
                color=self.color,
                stock_quantity=5,
                price=Decimal("29.99"),
            )


class CartModelTestCase(TestCase):
    """Test cases for Cart and CartItem models."""

    def setUp(self):
        """Set up test data."""
        self.user = create_test_user()

        self.product = Product.objects.create(
            name="Test T-Shirt", slug="test-tshirt", base_price=Decimal("29.99")
        )

        size = Size.objects.create(code="M", label="Medium")
        color = Color.objects.create(name="Black")

        self.variant = ProductVariant.objects.create(
            product=self.product, size=size, color=color, stock_quantity=10, price=Decimal("29.99")
        )

    def test_create_cart_for_user(self):
        """Test creating a cart for authenticated user."""
        cart = Cart.objects.create(user=self.user, is_active=True)

        self.assertEqual(cart.user, self.user)
        self.assertIsNone(cart.session_key)
        self.assertTrue(cart.is_active)

    def test_create_cart_for_anonymous(self):
        """Test creating a cart for anonymous user."""
        cart = Cart.objects.create(session_key="test_session_123", is_active=True)

        self.assertIsNone(cart.user)
        self.assertEqual(cart.session_key, "test_session_123")

    def test_add_item_to_cart(self):
        """Test adding items to cart."""
        cart = Cart.objects.create(user=self.user, is_active=True)

        cart_item = CartItem.objects.create(cart=cart, variant=self.variant, quantity=2)

        self.assertEqual(cart_item.cart, cart)
        self.assertEqual(cart_item.variant, self.variant)
        self.assertEqual(cart_item.quantity, 2)

    def test_cart_items_relationship(self):
        """Test cart items relationship."""
        cart = Cart.objects.create(user=self.user, is_active=True)

        CartItem.objects.create(cart=cart, variant=self.variant, quantity=2)
        CartItem.objects.create(cart=cart, variant=self.variant, quantity=1)

        self.assertEqual(cart.items.count(), 2)


class OrderModelTestCase(TestCase):
    """Test cases for Order and OrderItem models."""

    def setUp(self):
        """Set up test data."""
        self.user = create_test_user()

        self.product = Product.objects.create(
            name="Test T-Shirt", slug="test-tshirt", base_price=Decimal("29.99")
        )

        size = Size.objects.create(code="M", label="Medium")
        color = Color.objects.create(name="Black")

        self.variant = ProductVariant.objects.create(
            product=self.product, size=size, color=color, stock_quantity=10, price=Decimal("29.99")
        )

    def test_create_order(self):
        """Test creating an order."""
        order = Order.objects.create(
            user=self.user,
            email=self.user.email,
            status=OrderStatus.CREATED,
            subtotal=Decimal("29.99"),
            shipping=Decimal("10.00"),
            tax=Decimal("2.10"),
            total=Decimal("42.09"),
        )

        self.assertEqual(order.user, self.user)
        self.assertEqual(order.status, OrderStatus.CREATED)
        self.assertEqual(order.total, Decimal("42.09"))

    def test_order_status_choices(self):
        """Test order status choices."""
        order = Order.objects.create(
            user=self.user, email=self.user.email, status=OrderStatus.CREATED
        )

        # Test status transitions
        order.status = OrderStatus.AWAITING_PAYMENT
        order.save()
        self.assertEqual(order.status, OrderStatus.AWAITING_PAYMENT)

        order.status = OrderStatus.PAID
        order.save()
        self.assertEqual(order.status, OrderStatus.PAID)

        order.status = OrderStatus.SHIPPED
        order.save()
        self.assertEqual(order.status, OrderStatus.SHIPPED)

        order.status = OrderStatus.FULFILLED
        order.save()
        self.assertEqual(order.status, OrderStatus.FULFILLED)

    def test_create_order_item(self):
        """Test creating an order item."""
        order = Order.objects.create(
            user=self.user, email=self.user.email, status=OrderStatus.CREATED
        )

        order_item = OrderItem.objects.create(
            order=order,
            variant=self.variant,
            sku="TEST-SKU-123",
            quantity=2,
            line_total=Decimal("59.98"),
        )

        self.assertEqual(order_item.order, order)
        self.assertEqual(order_item.variant, self.variant)
        self.assertEqual(order_item.quantity, 2)
        self.assertEqual(order_item.line_total, Decimal("59.98"))

    def test_order_items_relationship(self):
        """Test order items relationship."""
        order = Order.objects.create(
            user=self.user, email=self.user.email, status=OrderStatus.CREATED
        )

        OrderItem.objects.create(
            order=order, variant=self.variant, sku="SKU-1", quantity=2, line_total=Decimal("59.98")
        )

        OrderItem.objects.create(
            order=order, variant=self.variant, sku="SKU-2", quantity=1, line_total=Decimal("29.99")
        )

        self.assertEqual(order.items.count(), 2)

    def test_order_with_addresses(self):
        """Test order with shipping and billing addresses."""
        shipping_address = Address.objects.create(
            full_name="John Doe",
            line1="123 Main St",
            city="Chicago",
            region="IL",
            postal_code="60601",
            country="US",
            email="test@example.com",
        )

        billing_address = Address.objects.create(
            full_name="John Doe",
            line1="456 Office Blvd",
            city="Chicago",
            region="IL",
            postal_code="60602",
            country="US",
            email="test@example.com",
        )

        order = Order.objects.create(
            user=self.user,
            email=self.user.email,
            status=OrderStatus.CREATED,
            shipping_address=shipping_address,
            billing_address=billing_address,
        )

        self.assertEqual(order.shipping_address, shipping_address)
        self.assertEqual(order.billing_address, billing_address)


class SizeColorModelTestCase(TestCase):
    """Test cases for Size and Color models."""

    def test_create_size(self):
        """Test creating a size."""
        size = Size.objects.create(code="L", label="Large")

        self.assertEqual(size.code, "L")
        self.assertEqual(size.label, "Large")
        self.assertEqual(str(size), "Large")

    def test_size_without_label(self):
        """Test size without label uses code."""
        size = Size.objects.create(code="XL")

        self.assertEqual(str(size), "XL")

    def test_create_color(self):
        """Test creating a color."""
        color = Color.objects.create(name="Red")

        self.assertEqual(color.name, "Red")
        self.assertEqual(str(color), "Red")
