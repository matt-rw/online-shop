"""
Stripe webhook handlers for processing payment events.
"""
import logging
import stripe
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Order, OrderStatus

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY


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
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    # Verify webhook signature (set STRIPE_WEBHOOK_SECRET in settings)
    webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)

    try:
        if webhook_secret:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        else:
            # For development without webhook secret
            event = stripe.Event.construct_from(
                stripe.util.json.loads(payload), stripe.api_key
            )

    except ValueError as e:
        # Invalid payload
        logger.error(f"Invalid webhook payload: {e}")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        logger.error(f"Invalid webhook signature: {e}")
        return HttpResponse(status=400)

    # Handle the event
    event_type = event['type']

    logger.info(f"Received Stripe webhook: {event_type}")

    if event_type == 'checkout.session.completed':
        handle_checkout_session_completed(event)
    elif event_type == 'payment_intent.succeeded':
        handle_payment_intent_succeeded(event)
    elif event_type == 'payment_intent.payment_failed':
        handle_payment_intent_failed(event)
    else:
        logger.info(f"Unhandled event type: {event_type}")

    return JsonResponse({'status': 'success'})


def handle_checkout_session_completed(event):
    """
    Handle successful checkout session completion.
    Update order status and send confirmation email.
    """
    session = event['data']['object']
    checkout_session_id = session['id']
    payment_intent_id = session.get('payment_intent')

    try:
        order = Order.objects.get(stripe_checkout_id=checkout_session_id)

        # Update order with payment info
        order.status = OrderStatus.PAID
        order.stripe_payment_intent_id = payment_intent_id

        # Get customer email from session if not already set
        if not order.email and session.get('customer_details', {}).get('email'):
            order.email = session['customer_details']['email']

        order.save()

        logger.info(f"Order {order.id} marked as PAID (session: {checkout_session_id})")

        # TODO: Send order confirmation email
        # send_order_confirmation_email(order)

        # TODO: Notify admin of new order
        # notify_admin_new_order(order)

    except Order.DoesNotExist:
        logger.error(f"Order not found for checkout session: {checkout_session_id}")
    except Exception as e:
        logger.error(f"Error handling checkout completion: {e}")


def handle_payment_intent_succeeded(event):
    """
    Handle successful payment intent.
    This is a backup to checkout.session.completed.
    """
    payment_intent = event['data']['object']
    payment_intent_id = payment_intent['id']

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
    payment_intent = event['data']['object']
    payment_intent_id = payment_intent['id']

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
