"""
Stripe webhook handlers for processing payment events.
"""

import logging
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

import stripe

from .models import Cart, Order, OrderItem, OrderStatus

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY
User = get_user_model()


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """
    Handle Stripe webhook events.

    Main events to handle:
    - checkout.session.completed: Payment succeeded
    - payment_intent.succeeded: Payment processed
    - payment_intent.payment_failed: Payment failed
    """
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

    # Verify webhook signature (REQUIRED in production)
    webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)

    # SECURITY: Webhook secret is required in production to prevent forged requests
    if not webhook_secret:
        if settings.DEBUG:
            # Development only: allow unsigned webhooks with warning
            import json
            logger.warning("STRIPE_WEBHOOK_SECRET not set - accepting unsigned webhook (DEV ONLY)")
            try:
                event = json.loads(payload)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid webhook JSON: {e}")
                return HttpResponse(status=400)
        else:
            # Production: reject unsigned webhooks
            logger.error("STRIPE_WEBHOOK_SECRET not configured - rejecting webhook")
            return HttpResponse("Webhook secret not configured", status=500)
    else:
        # Verify signature (production path)
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except stripe.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {e}")
            return HttpResponse(status=400)
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {e}")
            return HttpResponse(status=400)
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return HttpResponse(status=400)

    # Handle the event
    event_type = event["type"]

    logger.info(f"Received Stripe webhook: {event_type}")

    if event_type == "checkout.session.completed":
        handle_checkout_session_completed(event)
    elif event_type == "payment_intent.succeeded":
        handle_payment_intent_succeeded(event)
    elif event_type == "payment_intent.payment_failed":
        handle_payment_intent_failed(event)
    else:
        logger.info(f"Unhandled event type: {event_type}")

    return JsonResponse({"status": "success"})


def handle_checkout_session_completed(event):
    """
    Handle successful checkout session completion.
    Create order from cart and metadata, then clear cart.
    """
    session = event["data"]["object"]
    checkout_session_id = session["id"]
    payment_intent_id = session.get("payment_intent")
    metadata = session.get("metadata", {})

    try:
        # Check if order already exists (idempotency)
        existing_order = Order.objects.filter(stripe_checkout_id=checkout_session_id).first()
        if existing_order:
            logger.info(f"Order {existing_order.id} already exists for session {checkout_session_id}")
            if existing_order.status != OrderStatus.PAID:
                existing_order.status = OrderStatus.PAID
                existing_order.stripe_payment_intent_id = payment_intent_id
                existing_order.save()
            return

        # Get cart
        cart_id = metadata.get("cart_id")
        if not cart_id:
            logger.error(f"No cart_id in metadata for session: {checkout_session_id}")
            return

        try:
            cart = Cart.objects.get(id=cart_id)
        except Cart.DoesNotExist:
            logger.error(f"Cart {cart_id} not found for session: {checkout_session_id}")
            return

        cart_items = cart.items.select_related("variant__product").all()
        if not cart_items.exists():
            logger.error(f"Cart {cart_id} is empty for session: {checkout_session_id}")
            return

        # Get user if exists
        user = None
        user_id = metadata.get("user_id")
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass

        # Get customer email
        customer_email = metadata.get("customer_email") or ""
        if not customer_email and session.get("customer_details", {}).get("email"):
            customer_email = session["customer_details"]["email"]

        # Parse amounts from metadata
        subtotal = Decimal(metadata.get("subtotal", "0"))
        shipping_cost = Decimal(metadata.get("shipping_cost", "0"))

        # Create the order
        order = Order.objects.create(
            user=user,
            email=customer_email,
            status=OrderStatus.PAID,
            subtotal=subtotal,
            shipping=shipping_cost,
            tax=Decimal("0.00"),
            total=subtotal + shipping_cost,
            stripe_checkout_id=checkout_session_id,
            stripe_payment_intent_id=payment_intent_id,
        )

        # Create order items from cart
        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                variant=item.variant,
                sku=str(item.variant.id),
                quantity=item.quantity,
                line_total=item.variant.price * item.quantity,
            )

        # Clear the cart
        cart.items.all().delete()
        cart.is_active = False
        cart.save()

        logger.info(f"Order {order.id} created and marked as PAID (session: {checkout_session_id})")

        # TODO: Send order confirmation email
        # send_order_confirmation_email(order)

        # TODO: Notify admin of new order
        # notify_admin_new_order(order)

    except Exception as e:
        logger.error(f"Error handling checkout completion: {e}")


def handle_payment_intent_succeeded(event):
    """
    Handle successful payment intent.
    This is a backup to checkout.session.completed.
    """
    payment_intent = event["data"]["object"]
    payment_intent_id = payment_intent["id"]

    try:
        order = Order.objects.get(stripe_payment_intent_id=payment_intent_id)

        if order.status != OrderStatus.PAID:
            order.status = OrderStatus.PAID
            order.save()
            logger.info(f"Order {order.id} marked as PAID via payment_intent")

    except Order.DoesNotExist:
        logger.warning(f"No order found for payment_intent: {payment_intent_id}")
    except Exception as e:
        logger.error(f"Error handling payment intent succeeded: {e}")


def handle_payment_intent_failed(event):
    """
    Handle failed payment intent.
    Mark order as failed.
    """
    payment_intent = event["data"]["object"]
    payment_intent_id = payment_intent["id"]

    try:
        order = Order.objects.get(stripe_payment_intent_id=payment_intent_id)
        order.status = OrderStatus.FAILED
        order.save()

        logger.warning(f"Order {order.id} marked as FAILED")

        # TODO: Send payment failure notification to customer
        # send_payment_failed_email(order)

    except Order.DoesNotExist:
        logger.warning(f"No order found for failed payment_intent: {payment_intent_id}")
    except Exception as e:
        logger.error(f"Error handling payment intent failed: {e}")
