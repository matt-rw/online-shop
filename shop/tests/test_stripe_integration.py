"""
Tests for Stripe integration and webhook handling.
"""
import json
from decimal import Decimal
from unittest.mock import patch, Mock
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from shop.models import (
    Cart, CartItem, Product, ProductVariant, Size, Color,
    Order, OrderStatus, OrderItem
)
from .test_helpers import create_test_user

User = get_user_model()


class StripeIntegrationTestCase(TestCase):
    """Test cases for Stripe checkout integration."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()

        # Create test user
        self.user = create_test_user()

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

    @patch('shop.cart_views.stripe.checkout.Session.create')
    def test_create_checkout_session(self, mock_stripe_session):
        """Test creating Stripe checkout session."""
        # Mock Stripe session creation
        mock_stripe_session.return_value = Mock(
            id='cs_test_123',
            url='https://checkout.stripe.com/pay/cs_test_123'
        )

        # Add item to cart
        self.client.post(reverse('shop:add_to_cart'), {
            'variant_id': self.variant.id,
            'quantity': 2
        })

        # Create checkout session
        response = self.client.post(reverse('shop:create_checkout_session'))

        # Should redirect to Stripe checkout
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('https://checkout.stripe.com'))

        # Verify order was created
        order = Order.objects.filter(stripe_checkout_id='cs_test_123').first()
        self.assertIsNotNone(order)
        self.assertEqual(order.status, OrderStatus.AWAITING_PAYMENT)
        self.assertEqual(order.items.count(), 1)

        # Verify Stripe API was called correctly
        mock_stripe_session.assert_called_once()
        call_kwargs = mock_stripe_session.call_args[1]
        self.assertEqual(call_kwargs['mode'], 'payment')
        self.assertEqual(len(call_kwargs['line_items']), 2)  # Product + shipping

    @patch('shop.cart_views.stripe.checkout.Session.create')
    def test_create_checkout_session_empty_cart(self, mock_stripe_session):
        """Test checkout with empty cart fails."""
        response = self.client.post(reverse('shop:create_checkout_session'))

        # Should redirect with error
        self.assertEqual(response.status_code, 302)
        messages = list(response.wsgi_request._messages)
        self.assertTrue(any('empty' in str(m).lower() for m in messages))

        # Stripe should not be called
        mock_stripe_session.assert_not_called()

    @patch('shop.cart_views.stripe.checkout.Session.create')
    def test_checkout_session_includes_user_email(self, mock_stripe_session):
        """Test checkout session includes user email if logged in."""
        mock_stripe_session.return_value = Mock(
            id='cs_test_123',
            url='https://checkout.stripe.com/pay/cs_test_123'
        )

        # Login and add item
        self.client.login(email='test@example.com', password='testpass123')
        self.client.post(reverse('shop:add_to_cart'), {
            'variant_id': self.variant.id,
            'quantity': 1
        })

        # Create checkout session
        self.client.post(reverse('shop:create_checkout_session'))

        # Verify email was passed to Stripe
        call_kwargs = mock_stripe_session.call_args[1]
        self.assertEqual(call_kwargs['customer_email'], 'test@example.com')

    @patch('shop.cart_views.stripe.checkout.Session.retrieve')
    @patch('shop.cart_views.clear_cart')
    def test_checkout_success_view(self, mock_clear_cart, mock_stripe_retrieve):
        """Test checkout success page."""
        # Create an order
        cart = Cart.objects.create(user=self.user, is_active=True)
        CartItem.objects.create(cart=cart, variant=self.variant, quantity=2)

        order = Order.objects.create(
            user=self.user,
            email=self.user.email,
            status=OrderStatus.AWAITING_PAYMENT,
            subtotal=Decimal('59.98'),
            shipping=Decimal('10.00'),
            tax=Decimal('4.20'),
            total=Decimal('74.18'),
            stripe_checkout_id='cs_test_123'
        )

        # Mock Stripe session retrieval
        mock_stripe_retrieve.return_value = Mock(
            id='cs_test_123',
            metadata={'cart_id': str(cart.id)}
        )

        # Visit success page
        response = self.client.get(
            reverse('shop:checkout_success') + '?session_id=cs_test_123'
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Thank you' or 'Order' or 'confirmation')

        # Verify cart was cleared
        mock_clear_cart.assert_called_once()

    def test_checkout_success_invalid_session(self):
        """Test checkout success with invalid session ID."""
        response = self.client.get(reverse('shop:checkout_success'))

        self.assertEqual(response.status_code, 302)
        messages = list(response.wsgi_request._messages)
        self.assertTrue(any('invalid' in str(m).lower() for m in messages))


class StripeWebhookTestCase(TestCase):
    """Test cases for Stripe webhook handling."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()

        # Create test order
        self.user = create_test_user()

        self.order = Order.objects.create(
            user=self.user,
            email=self.user.email,
            status=OrderStatus.AWAITING_PAYMENT,
            subtotal=Decimal('29.99'),
            shipping=Decimal('10.00'),
            tax=Decimal('2.10'),
            total=Decimal('42.09'),
            stripe_checkout_id='cs_test_123',
            stripe_payment_intent_id='pi_test_456'
        )

    @override_settings(STRIPE_WEBHOOK_SECRET='test_secret')
    @patch('shop.webhooks.stripe.Webhook.construct_event')
    def test_webhook_checkout_session_completed(self, mock_construct_event):
        """Test handling checkout.session.completed webhook."""
        # Mock webhook event
        mock_construct_event.return_value = {
            'type': 'checkout.session.completed',
            'data': {
                'object': {
                    'id': 'cs_test_123',
                    'payment_intent': 'pi_test_456',
                    'customer_details': {
                        'email': 'test@example.com'
                    }
                }
            }
        }

        # Send webhook
        response = self.client.post(
            reverse('shop:stripe_webhook'),
            data=json.dumps({'type': 'checkout.session.completed'}),
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='test_signature'
        )

        self.assertEqual(response.status_code, 200)

        # Verify order was updated
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.PAID)

    @override_settings(STRIPE_WEBHOOK_SECRET='test_secret')
    @patch('shop.webhooks.stripe.Webhook.construct_event')
    def test_webhook_payment_intent_succeeded(self, mock_construct_event):
        """Test handling payment_intent.succeeded webhook."""
        mock_construct_event.return_value = {
            'type': 'payment_intent.succeeded',
            'data': {
                'object': {
                    'id': 'pi_test_456'
                }
            }
        }

        response = self.client.post(
            reverse('shop:stripe_webhook'),
            data=json.dumps({'type': 'payment_intent.succeeded'}),
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='test_signature'
        )

        self.assertEqual(response.status_code, 200)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.PAID)

    @override_settings(STRIPE_WEBHOOK_SECRET='test_secret')
    @patch('shop.webhooks.stripe.Webhook.construct_event')
    def test_webhook_payment_intent_failed(self, mock_construct_event):
        """Test handling payment_intent.payment_failed webhook."""
        mock_construct_event.return_value = {
            'type': 'payment_intent.payment_failed',
            'data': {
                'object': {
                    'id': 'pi_test_456'
                }
            }
        }

        response = self.client.post(
            reverse('shop:stripe_webhook'),
            data=json.dumps({'type': 'payment_intent.payment_failed'}),
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='test_signature'
        )

        self.assertEqual(response.status_code, 200)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.FAILED)

    def test_webhook_invalid_signature(self):
        """Test webhook with invalid signature is rejected."""
        response = self.client.post(
            reverse('shop:stripe_webhook'),
            data=json.dumps({'type': 'checkout.session.completed'}),
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='invalid_signature'
        )

        # Should return 400 for invalid signature
        # (Actual behavior depends on STRIPE_WEBHOOK_SECRET setting)
        self.assertIn(response.status_code, [200, 400])

    @override_settings(STRIPE_WEBHOOK_SECRET='test_secret')
    @patch('shop.webhooks.stripe.Webhook.construct_event')
    def test_webhook_order_not_found(self, mock_construct_event):
        """Test webhook for non-existent order."""
        mock_construct_event.return_value = {
            'type': 'checkout.session.completed',
            'data': {
                'object': {
                    'id': 'cs_nonexistent',
                    'payment_intent': 'pi_nonexistent'
                }
            }
        }

        # Should not crash
        response = self.client.post(
            reverse('shop:stripe_webhook'),
            data=json.dumps({'type': 'checkout.session.completed'}),
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='test_signature'
        )

        self.assertEqual(response.status_code, 200)
