"""
SMS webhook handlers for processing incoming messages.
Supports Telnyx and Twilio webhooks.
"""
import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

# Keywords for opt-out (case insensitive)
OPT_OUT_KEYWORDS = {"stop", "unsubscribe", "cancel", "end", "quit"}

# Keywords for opt-in (case insensitive)
OPT_IN_KEYWORDS = {"start", "subscribe", "unstop", "yes"}

# Keywords for help
HELP_KEYWORDS = {"help", "info"}


@csrf_exempt
@require_POST
def telnyx_webhook(request):
    """
    Handle incoming Telnyx webhook events.

    Telnyx sends webhooks for:
    - message.received: Incoming SMS
    - message.sent: Delivery confirmation
    - message.finalized: Final delivery status

    Webhook URL to configure in Telnyx: https://yourdomain.com/webhook/sms/telnyx/
    """
    try:
        # Verify webhook signature if secret is configured
        webhook_secret = getattr(settings, "TELNYX_WEBHOOK_SECRET", None)

        if webhook_secret:
            signature = request.headers.get("telnyx-signature-ed25519", "")
            timestamp = request.headers.get("telnyx-timestamp", "")

            if not _verify_telnyx_signature(request.body, signature, timestamp, webhook_secret):
                logger.warning("Invalid Telnyx webhook signature")
                return HttpResponse("Invalid signature", status=401)

        # Parse the webhook payload
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid Telnyx webhook JSON: {e}")
            return HttpResponse("Invalid JSON", status=400)

        # Get event data
        data = payload.get("data", {})
        event_type = data.get("event_type", "")
        event_payload = data.get("payload", {})

        logger.info(f"Received Telnyx webhook: {event_type}")

        # Handle incoming message
        if event_type == "message.received":
            from_number = event_payload.get("from", {}).get("phone_number", "")
            to_number = event_payload.get("to", [{}])[0].get("phone_number", "")
            message_text = event_payload.get("text", "").strip().lower()

            logger.info(f"Incoming SMS from {from_number}: {message_text[:50]}...")

            # Process the message
            _process_incoming_message(from_number, to_number, message_text)

        # Handle delivery status updates
        elif event_type in ["message.sent", "message.finalized"]:
            message_id = event_payload.get("id", "")
            status = event_payload.get("to", [{}])[0].get("status", "")

            logger.info(f"Telnyx delivery status for {message_id}: {status}")
            _update_delivery_status(message_id, status, "telnyx")

        return HttpResponse("OK", status=200)

    except Exception as e:
        logger.error(f"Error processing Telnyx webhook: {e}")
        return HttpResponse("Error", status=500)


@csrf_exempt
@require_POST
def twilio_webhook(request):
    """
    Handle incoming Twilio webhook events.

    Twilio sends webhooks for incoming SMS to your configured webhook URL.

    Webhook URL to configure in Twilio: https://yourdomain.com/webhook/sms/twilio/
    """
    try:
        # Twilio sends form-encoded data
        from_number = request.POST.get("From", "")
        to_number = request.POST.get("To", "")
        message_text = request.POST.get("Body", "").strip().lower()
        message_sid = request.POST.get("MessageSid", "")

        logger.info(f"Incoming SMS from {from_number} (Twilio SID: {message_sid}): {message_text[:50]}...")

        # Process the message
        response_text = _process_incoming_message(from_number, to_number, message_text)

        # Return TwiML response
        # If you want to auto-reply, you can return a TwiML response
        if response_text:
            twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{response_text}</Message></Response>'
            return HttpResponse(twiml, content_type="application/xml")

        return HttpResponse("OK", status=200)

    except Exception as e:
        logger.error(f"Error processing Twilio webhook: {e}")
        return HttpResponse("Error", status=500)


def _process_incoming_message(from_number, to_number, message_text):
    """
    Process an incoming SMS message and take appropriate action.

    Args:
        from_number: The sender's phone number
        to_number: Your Telnyx/Twilio phone number
        message_text: The message content (already lowercased)

    Returns:
        str or None: Response message to send back (if any)
    """
    from shop.utils.sms_helper import handle_opt_in, handle_opt_out, send_sms

    # Check for opt-out keywords
    if message_text in OPT_OUT_KEYWORDS:
        handle_opt_out(from_number)

        # Send confirmation (required by carriers)
        confirmation = "You have been unsubscribed from Blueprint Apparel texts. Reply START to resubscribe."
        send_sms(from_number, confirmation)

        logger.info(f"Processed opt-out for {from_number}")
        return confirmation

    # Check for opt-in keywords
    if message_text in OPT_IN_KEYWORDS:
        if handle_opt_in(from_number):
            confirmation = "Welcome back! You are now subscribed to Blueprint Apparel texts. Reply STOP to unsubscribe."
            send_sms(from_number, confirmation)
            logger.info(f"Processed opt-in for {from_number}")
            return confirmation
        else:
            # New subscriber - they need to sign up through the website
            response = "To subscribe, please visit our website. Reply STOP to unsubscribe."
            send_sms(from_number, response)
            return response

    # Check for help keywords
    if message_text in HELP_KEYWORDS:
        help_text = "Blueprint Apparel: Get updates on sales & new products. Reply STOP to unsubscribe. Msg & data rates may apply."
        send_sms(from_number, help_text)
        return help_text

    # For any other message, you could:
    # 1. Log it for manual review
    # 2. Forward to support
    # 3. Auto-reply with help text
    logger.info(f"Unhandled incoming SMS from {from_number}: {message_text}")

    # Optional: Log to database for review
    _log_incoming_message(from_number, to_number, message_text)

    return None


def _log_incoming_message(from_number, to_number, message_text):
    """Log incoming message for review."""
    from shop.models import SMSLog, SMSSubscription

    try:
        subscription = SMSSubscription.objects.filter(phone_number=from_number).first()

        SMSLog.objects.create(
            subscription=subscription,
            phone_number=from_number,
            message_body=f"[INCOMING] {message_text}",
            status="received",
        )
    except Exception as e:
        logger.error(f"Error logging incoming message: {e}")


def _update_delivery_status(message_id, status, provider):
    """Update delivery status in SMSLog based on provider callback."""
    from shop.models import SMSLog

    # Map provider status to our status
    status_map = {
        # Telnyx statuses
        "delivered": "delivered",
        "sent": "sent",
        "failed": "failed",
        "delivery_failed": "failed",
        "sending_failed": "failed",
        # Twilio statuses
        "delivered": "delivered",
        "sent": "sent",
        "undelivered": "undelivered",
        "failed": "failed",
    }

    mapped_status = status_map.get(status.lower(), status.lower())

    try:
        # Find the log entry by provider message ID
        log = SMSLog.objects.filter(provider_message_id=message_id).first()

        if log:
            log.status = mapped_status
            if mapped_status == "delivered":
                from django.utils import timezone
                log.delivered_at = timezone.now()
            log.save()
            logger.info(f"Updated delivery status for {message_id}: {mapped_status}")
        else:
            logger.warning(f"No SMS log found for message ID: {message_id}")

    except Exception as e:
        logger.error(f"Error updating delivery status: {e}")


def _verify_telnyx_signature(payload, signature, timestamp, secret):
    """
    Verify Telnyx webhook signature.

    Note: Telnyx uses Ed25519 signatures. For full verification,
    you'd need the telnyx library or nacl/cryptography.
    This is a simplified check - for production, use proper Ed25519 verification.
    """
    # For now, just check that signature exists
    # Full Ed25519 verification requires additional dependencies
    if not signature or not timestamp:
        return False

    # TODO: Implement full Ed25519 signature verification
    # For now, accept if signature header is present
    # In production, use: telnyx.Webhook.construct_event(payload, signature, timestamp)
    return True
