"""
Tests for cart utility functions.
"""
from decimal import Decimal
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware

from shop.models import Cart, CartItem, Product, ProductVariant, Size, Color
from shop.cart_utils import (
    get_or_create_cart,
    add_to_cart,
    update_cart_item_quantity,
    remove_from_cart,
    get_cart_total,
    get_cart_count,
    merge_carts,
    clear_cart
)

User = get_user_model()


class CartUtilsTestCase(TestCase):
    """Test cases for cart utility functions."""

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()

        # Create test user
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        # Create test products
        self.product = Product.objects.create(
            name='Test T-Shirt',
            slug='test-tshirt',
            base_price=Decimal('29.99'),
            is_active=True
        )

        self.size = Size.objects.create(code='M', label='Medium')
        self.color = Color.objects.create(name='Black')

        self.variant = ProductVariant.objects.create(
            product=self.product,
            size=self.size,
            color=self.color,
            stock_quantity=10,
            price=Decimal('29.99'),
            is_active=True
        )

    def _add_session_to_request(self, request):
        """Add session to request."""
        middleware = SessionMiddleware(lambda x: None)
        middleware.process_request(request)
        request.session.save()
        return request

    def test_get_or_create_cart_authenticated(self):
        """Test getting or creating cart for authenticated user."""
        request = self.factory.get('/')
        request.user = self.user
        request = self._add_session_to_request(request)

        cart = get_or_create_cart(request)

        self.assertIsNotNone(cart)
        self.assertEqual(cart.user, self.user)
        self.assertTrue(cart.is_active)

        # Get same cart again
        cart2 = get_or_create_cart(request)
        self.assertEqual(cart.id, cart2.id)

    def test_get_or_create_cart_anonymous(self):
        """Test getting or creating cart for anonymous user."""
        request = self.factory.get('/')
        request.user = User()  # Anonymous user
        request = self._add_session_to_request(request)

        cart = get_or_create_cart(request)

        self.assertIsNotNone(cart)
        self.assertIsNone(cart.user)
        self.assertEqual(cart.session_key, request.session.session_key)
        self.assertTrue(cart.is_active)

    def test_add_to_cart_new_item(self):
        """Test adding a new item to cart."""
        request = self.factory.post('/')
        request.user = self.user
        request = self._add_session_to_request(request)

        cart_item, created = add_to_cart(request, self.variant.id, quantity=2)

        self.assertTrue(created)
        self.assertEqual(cart_item.variant, self.variant)
        self.assertEqual(cart_item.quantity, 2)

    def test_add_to_cart_existing_item(self):
        """Test adding to existing cart item (should update quantity)."""
        request = self.factory.post('/')
        request.user = self.user
        request = self._add_session_to_request(request)

        # Add item first time
        cart_item1, created1 = add_to_cart(request, self.variant.id, quantity=2)
        self.assertTrue(created1)

        # Add same item again
        cart_item2, created2 = add_to_cart(request, self.variant.id, quantity=3)
        self.assertFalse(created2)
        self.assertEqual(cart_item2.id, cart_item1.id)
        self.assertEqual(cart_item2.quantity, 5)  # 2 + 3

    def test_add_to_cart_invalid_variant(self):
        """Test adding invalid variant raises error."""
        request = self.factory.post('/')
        request.user = self.user
        request = self._add_session_to_request(request)

        with self.assertRaises(ValueError):
            add_to_cart(request, 99999, quantity=1)

    def test_update_cart_item_quantity(self):
        """Test updating cart item quantity."""
        request = self.factory.post('/')
        request.user = self.user
        request = self._add_session_to_request(request)

        cart_item, _ = add_to_cart(request, self.variant.id, quantity=2)

        # Update quantity
        updated_item = update_cart_item_quantity(
            cart_item.id,
            quantity=5,
            user=self.user
        )

        self.assertIsNotNone(updated_item)
        self.assertEqual(updated_item.quantity, 5)

    def test_update_cart_item_quantity_to_zero_deletes(self):
        """Test updating quantity to 0 deletes the item."""
        request = self.factory.post('/')
        request.user = self.user
        request = self._add_session_to_request(request)

        cart_item, _ = add_to_cart(request, self.variant.id, quantity=2)

        # Update to 0
        result = update_cart_item_quantity(
            cart_item.id,
            quantity=0,
            user=self.user
        )

        self.assertIsNone(result)
        self.assertFalse(CartItem.objects.filter(id=cart_item.id).exists())

    def test_remove_from_cart(self):
        """Test removing item from cart."""
        request = self.factory.post('/')
        request.user = self.user
        request = self._add_session_to_request(request)

        cart_item, _ = add_to_cart(request, self.variant.id, quantity=2)

        # Remove item
        result = remove_from_cart(cart_item.id, user=self.user)

        self.assertTrue(result)
        self.assertFalse(CartItem.objects.filter(id=cart_item.id).exists())

    def test_get_cart_total(self):
        """Test calculating cart total."""
        request = self.factory.post('/')
        request.user = self.user
        request = self._add_session_to_request(request)

        cart = get_or_create_cart(request)

        # Add items
        add_to_cart(request, self.variant.id, quantity=2)

        # Create another variant
        variant2 = ProductVariant.objects.create(
            product=self.product,
            size=self.size,
            color=self.color,
            stock_quantity=10,
            price=Decimal('39.99'),
            is_active=True
        )
        add_to_cart(request, variant2.id, quantity=1)

        total = get_cart_total(cart)

        # 2 * 29.99 + 1 * 39.99 = 99.97
        expected = (Decimal('29.99') * 2) + (Decimal('39.99') * 1)
        self.assertEqual(total, expected)

    def test_get_cart_count(self):
        """Test getting cart item count."""
        request = self.factory.post('/')
        request.user = self.user
        request = self._add_session_to_request(request)

        # Empty cart
        count = get_cart_count(request)
        self.assertEqual(count, 0)

        # Add items
        add_to_cart(request, self.variant.id, quantity=2)

        count = get_cart_count(request)
        self.assertEqual(count, 2)

    def test_merge_carts(self):
        """Test merging anonymous cart into user cart on login."""
        # Create anonymous cart
        anon_request = self.factory.post('/')
        anon_request.user = User()  # Anonymous
        anon_request = self._add_session_to_request(anon_request)

        anon_cart = get_or_create_cart(anon_request)
        add_to_cart(anon_request, self.variant.id, quantity=3)

        session_key = anon_request.session.session_key

        # Create user cart with different item
        variant2 = ProductVariant.objects.create(
            product=self.product,
            size=self.size,
            color=self.color,
            stock_quantity=10,
            price=Decimal('39.99'),
            is_active=True
        )

        user_cart = Cart.objects.create(user=self.user, is_active=True)
        CartItem.objects.create(cart=user_cart, variant=variant2, quantity=1)

        # Merge carts
        merged_cart = merge_carts(self.user, session_key)

        self.assertEqual(merged_cart.user, self.user)
        self.assertEqual(merged_cart.items.count(), 2)

        # Anonymous cart should be inactive
        anon_cart.refresh_from_db()
        self.assertFalse(anon_cart.is_active)

    def test_merge_carts_same_item(self):
        """Test merging carts with same item adds quantities."""
        # Create anonymous cart
        anon_request = self.factory.post('/')
        anon_request.user = User()  # Anonymous
        anon_request = self._add_session_to_request(anon_request)

        add_to_cart(anon_request, self.variant.id, quantity=3)
        session_key = anon_request.session.session_key

        # Create user cart with same item
        user_cart = Cart.objects.create(user=self.user, is_active=True)
        CartItem.objects.create(cart=user_cart, variant=self.variant, quantity=2)

        # Merge carts
        merged_cart = merge_carts(self.user, session_key)

        # Should have 1 item with combined quantity
        self.assertEqual(merged_cart.items.count(), 1)
        item = merged_cart.items.first()
        self.assertEqual(item.quantity, 5)  # 3 + 2

    def test_clear_cart(self):
        """Test clearing all items from cart."""
        request = self.factory.post('/')
        request.user = self.user
        request = self._add_session_to_request(request)

        cart = get_or_create_cart(request)
        add_to_cart(request, self.variant.id, quantity=2)

        self.assertEqual(cart.items.count(), 1)

        clear_cart(cart)

        self.assertEqual(cart.items.count(), 0)
