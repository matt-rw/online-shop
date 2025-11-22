"""
Tests for cart views.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from shop.models import Cart, CartItem, Color, Product, ProductVariant, Size

from .test_helpers import create_test_user

User = get_user_model()


class CartViewsTestCase(TestCase):
    """Test cases for cart views."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()

        # Create test user
        self.user = create_test_user()

        # Create test products
        self.product = Product.objects.create(
            name="Test T-Shirt", slug="test-tshirt", base_price=Decimal("29.99"), is_active=True
        )

        self.size = Size.objects.create(code="M", label="Medium")
        self.color = Color.objects.create(name="Black")

        self.variant = ProductVariant.objects.create(
            product=self.product,
            size=self.size,
            color=self.color,
            stock_quantity=10,
            price=Decimal("29.99"),
            is_active=True,
        )

    def test_cart_view_empty(self):
        """Test viewing empty cart."""
        response = self.client.get(reverse("shop:cart"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your cart is empty")

    def test_cart_view_with_items(self):
        """Test viewing cart with items."""
        # Add item to cart
        self.client.post(
            reverse("shop:add_to_cart"), {"variant_id": self.variant.id, "quantity": 2}
        )

        response = self.client.get(reverse("shop:cart"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)
        self.assertContains(response, "29.99")

    def test_add_to_cart_view(self):
        """Test adding item to cart."""
        response = self.client.post(
            reverse("shop:add_to_cart"), {"variant_id": self.variant.id, "quantity": 2}
        )

        self.assertEqual(response.status_code, 302)  # Redirect
        self.assertRedirects(response, reverse("shop:cart"))

        # Verify item was added
        session = self.client.session
        cart = Cart.objects.get(session_key=session.session_key, is_active=True)
        self.assertEqual(cart.items.count(), 1)

        cart_item = cart.items.first()
        self.assertEqual(cart_item.variant, self.variant)
        self.assertEqual(cart_item.quantity, 2)

    def test_add_to_cart_missing_variant(self):
        """Test adding to cart without variant_id."""
        response = self.client.post(reverse("shop:add_to_cart"), {"quantity": 2})

        # Should redirect back with error message
        self.assertEqual(response.status_code, 302)
        messages = list(response.wsgi_request._messages)
        self.assertTrue(any("select a product variant" in str(m) for m in messages))

    def test_add_to_cart_invalid_variant(self):
        """Test adding invalid variant to cart."""
        response = self.client.post(
            reverse("shop:add_to_cart"), {"variant_id": 99999, "quantity": 2}
        )

        self.assertEqual(response.status_code, 302)
        messages = list(response.wsgi_request._messages)
        self.assertTrue(any("not found" in str(m).lower() for m in messages))

    def test_add_to_cart_ajax(self):
        """Test adding to cart via AJAX returns JSON."""
        response = self.client.post(
            reverse("shop:add_to_cart"),
            {"variant_id": self.variant.id, "quantity": 2},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["cart_count"], 2)

    def test_update_cart_item_view(self):
        """Test updating cart item quantity."""
        # Add item first
        self.client.post(
            reverse("shop:add_to_cart"), {"variant_id": self.variant.id, "quantity": 2}
        )

        session = self.client.session
        cart = Cart.objects.get(session_key=session.session_key, is_active=True)
        cart_item = cart.items.first()

        # Update quantity
        response = self.client.post(
            reverse("shop:update_cart_item", args=[cart_item.id]), {"quantity": 5}
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("shop:cart"))

        cart_item.refresh_from_db()
        self.assertEqual(cart_item.quantity, 5)

    def test_update_cart_item_ajax(self):
        """Test updating cart item via AJAX."""
        # Add item first
        self.client.post(
            reverse("shop:add_to_cart"), {"variant_id": self.variant.id, "quantity": 2}
        )

        session = self.client.session
        cart = Cart.objects.get(session_key=session.session_key, is_active=True)
        cart_item = cart.items.first()

        # Update via AJAX
        response = self.client.post(
            reverse("shop:update_cart_item", args=[cart_item.id]),
            {"quantity": 5},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["cart_count"], 5)

    def test_remove_from_cart_view(self):
        """Test removing item from cart."""
        # Add item first
        self.client.post(
            reverse("shop:add_to_cart"), {"variant_id": self.variant.id, "quantity": 2}
        )

        session = self.client.session
        cart = Cart.objects.get(session_key=session.session_key, is_active=True)
        cart_item = cart.items.first()

        # Remove item
        response = self.client.post(reverse("shop:remove_from_cart", args=[cart_item.id]))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("shop:cart"))

        # Verify item was removed
        self.assertFalse(CartItem.objects.filter(id=cart_item.id).exists())

    def test_cart_persistence_authenticated_user(self):
        """Test cart persists for logged-in users."""
        self.client.login(email="test@example.com", password="testpass123")

        # Add item
        self.client.post(
            reverse("shop:add_to_cart"), {"variant_id": self.variant.id, "quantity": 2}
        )

        # Logout and login again
        self.client.logout()
        self.client.login(email="test@example.com", password="testpass123")

        # Cart should still have items
        response = self.client.get(reverse("shop:cart"))
        self.assertContains(response, self.product.name)

    def test_checkout_view_empty_cart(self):
        """Test checkout view redirects if cart is empty."""
        response = self.client.get(reverse("shop:checkout"))

        # Should redirect to cart with warning
        self.assertEqual(response.status_code, 302)
        messages = list(response.wsgi_request._messages)
        self.assertTrue(any("empty" in str(m).lower() for m in messages))

    def test_checkout_view_with_items(self):
        """Test checkout view displays with items in cart."""
        # Add item
        self.client.post(
            reverse("shop:add_to_cart"), {"variant_id": self.variant.id, "quantity": 2}
        )

        response = self.client.get(reverse("shop:checkout"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)
        self.assertContains(response, "Checkout")

    def test_unauthorized_cart_access(self):
        """Test users can't access other users' cart items."""
        # User 1 adds item
        self.client.login(email="test@example.com", password="testpass123")
        self.client.post(
            reverse("shop:add_to_cart"), {"variant_id": self.variant.id, "quantity": 2}
        )

        cart = Cart.objects.get(user=self.user, is_active=True)
        cart_item = cart.items.first()
        self.client.logout()

        # User 2 tries to update User 1's cart item
        user2 = create_test_user(email="test2@example.com")
        self.client.login(email="test2@example.com", password="testpass123")

        response = self.client.post(
            reverse("shop:update_cart_item", args=[cart_item.id]), {"quantity": 10}
        )

        # Should fail
        cart_item.refresh_from_db()
        self.assertEqual(cart_item.quantity, 2)  # Unchanged
