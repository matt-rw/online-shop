"""
SMS sending utilities.
Supports multiple providers: Telnyx (recommended), Twilio (legacy).
"""
import logging

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def get_sms_provider():
    """Get the configured SMS provider name."""
    return getattr(settings, "SMS_PROVIDER", "telnyx").lower()


def send_sms(phone_number, message, subscription=None, campaign=None, template=None, quick_message=None):
    """
    Send an SMS message using the configured provider and log the result.

    Args:
        phone_number (str): The recipient's phone number in E.164 format (e.g., +1234567890)
        message (str): The message body to send
        subscription (SMSSubscription, optional): The subscription object if available
        campaign (SMSCampaign, optional): The campaign this SMS belongs to
        template (SMSTemplate, optional): The template used for this SMS
        quick_message (QuickMessage, optional): The quick message this belongs to

    Returns:
        tuple: (success: bool, log_object: SMSLog)
    """
    from shop.models import SMSLog

    # Create log entry
    log = SMSLog.objects.create(
        subscription=subscription,
        phone_number=phone_number,
        message_body=message,
        campaign=campaign,
        template=template,
        quick_message=quick_message,
        status="queued",
    )

    provider = get_sms_provider()

    if provider == "telnyx":
        return _send_via_telnyx(phone_number, message, log, template)
    elif provider == "twilio":
        return _send_via_twilio(phone_number, message, log, template)
    elif provider == "plivo":
        return _send_via_plivo(phone_number, message, log, template)
    else:
        logger.error(f"Unknown SMS provider: {provider}")
        log.status = "failed"
        log.error_message = f"Unknown SMS provider: {provider}"
        log.save()
        return False, log


def _send_via_telnyx(phone_number, message, log, template=None):
    """Send SMS via Telnyx."""
    api_key = getattr(settings, "TELNYX_API_KEY", None)
    from_number = getattr(settings, "TELNYX_PHONE_NUMBER", None)
    messaging_profile_id = getattr(settings, "TELNYX_MESSAGING_PROFILE_ID", None)

    if not api_key or not from_number:
        logger.warning("Telnyx credentials not configured. SMS not sent.")
        log.status = "failed"
        log.error_message = "Telnyx not configured (missing API key or phone number)"
        log.save()
        return False, log

    try:
        from telnyx import Telnyx

        # Create client with API key
        client = Telnyx(api_key=api_key)

        # Send the message using the Telnyx SDK v4 API
        response = client.messages.send(
            from_=from_number,
            to=phone_number,
            text=message,
            messaging_profile_id=messaging_profile_id if messaging_profile_id else None,
        )

        # Update log with success
        log.status = "sent"
        log.provider_message_id = response.data.id if response.data else ""
        log.save()

        logger.info(f"SMS sent via Telnyx to {phone_number}. ID: {log.provider_message_id}")

        # Update template usage count if template was used
        if template:
            template.times_used += 1
            template.last_used = timezone.now()
            template.save(update_fields=["times_used", "last_used"])

        return True, log

    except Exception as e:
        logger.error(f"Failed to send SMS via Telnyx to {phone_number}: {str(e)}")
        log.status = "failed"
        log.error_message = str(e)
        log.save()
        return False, log


def _send_via_twilio(phone_number, message, log, template=None):
    """Send SMS via Twilio (legacy provider)."""
    account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", None)
    auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", None)
    from_number = getattr(settings, "TWILIO_PHONE_NUMBER", None)

    if not all([account_sid, auth_token, from_number]):
        logger.warning("Twilio credentials not configured. SMS not sent.")
        log.status = "failed"
        log.error_message = "Twilio not configured"
        log.save()
        return False, log

    try:
        from twilio.rest import Client

        client = Client(account_sid, auth_token)

        message_obj = client.messages.create(
            body=message,
            from_=from_number,
            to=phone_number
        )

        # Update log with success
        log.status = "sent"
        log.provider_message_id = message_obj.sid
        log.save()

        logger.info(f"SMS sent via Twilio to {phone_number}. SID: {message_obj.sid}")

        # Update template usage count if template was used
        if template:
            template.times_used += 1
            template.last_used = timezone.now()
            template.save(update_fields=["times_used", "last_used"])

        return True, log

    except Exception as e:
        logger.error(f"Failed to send SMS via Twilio to {phone_number}: {str(e)}")
        log.status = "failed"
        log.error_message = str(e)
        log.save()
        return False, log


def _send_via_plivo(phone_number, message, log, template=None):
    """Send SMS via Plivo."""
    auth_id = getattr(settings, "PLIVO_AUTH_ID", None)
    auth_token = getattr(settings, "PLIVO_AUTH_TOKEN", None)
    from_number = getattr(settings, "PLIVO_PHONE_NUMBER", None)

    if not all([auth_id, auth_token, from_number]):
        logger.warning("Plivo credentials not configured. SMS not sent.")
        log.status = "failed"
        log.error_message = "Plivo not configured (missing auth ID, token, or phone number)"
        log.save()
        return False, log

    try:
        import plivo

        client = plivo.RestClient(auth_id, auth_token)

        response = client.messages.create(
            src=from_number,
            dst=phone_number,
            text=message,
        )

        # Update log with success
        log.status = "sent"
        log.provider_message_id = response.message_uuid[0] if response.message_uuid else ""
        log.save()

        logger.info(f"SMS sent via Plivo to {phone_number}. UUID: {log.provider_message_id}")

        # Update template usage count if template was used
        if template:
            template.times_used += 1
            template.last_used = timezone.now()
            template.save(update_fields=["times_used", "last_used"])

        return True, log

    except Exception as e:
        logger.error(f"Failed to send SMS via Plivo to {phone_number}: {str(e)}")
        log.status = "failed"
        log.error_message = str(e)
        log.save()
        return False, log


def send_from_template(phone_number, template, context=None, subscription=None, campaign=None):
    """
    Send an SMS using a template.

    Args:
        phone_number (str): The recipient's phone number
        template (SMSTemplate): The template to use
        context (dict, optional): Variables to render in the template
        subscription (SMSSubscription, optional): The subscription object
        campaign (SMSCampaign, optional): The campaign this belongs to

    Returns:
        tuple: (success: bool, log_object: SMSLog)
    """
    if context is None:
        context = {}

    # Render the template
    message = template.render(**context)

    # Send the SMS
    return send_sms(
        phone_number=phone_number,
        message=message,
        subscription=subscription,
        campaign=campaign,
        template=template,
    )


def send_campaign(campaign):
    """
    Send an SMS campaign to all targeted subscribers.

    Args:
        campaign (SMSCampaign): The campaign to send

    Returns:
        dict: Statistics about the send (total, sent, failed)
    """
    from shop.models import SMSSubscription

    if campaign.status not in ["draft", "scheduled"]:
        logger.warning(f"Cannot send campaign {campaign.id} with status {campaign.status}")
        return {"error": "Invalid campaign status"}

    # Update campaign status
    campaign.status = "sending"
    campaign.started_at = timezone.now()
    campaign.save()

    # Get recipients (active and confirmed)
    if campaign.send_to_all_active:
        recipients = SMSSubscription.objects.filter(is_active=True, is_confirmed=True)
    else:
        recipients = SMSSubscription.objects.none()

    campaign.total_recipients = recipients.count()
    campaign.save()

    sent_count = 0
    failed_count = 0

    # Send to each recipient
    for subscription in recipients:
        success, log = send_from_template(
            phone_number=subscription.phone_number,
            template=campaign.template,
            subscription=subscription,
            campaign=campaign,
        )

        if success:
            sent_count += 1
        else:
            failed_count += 1

        # Update campaign progress
        campaign.sent_count = sent_count
        campaign.failed_count = failed_count
        campaign.save()

    # Mark campaign as complete
    campaign.status = "sent"
    campaign.completed_at = timezone.now()
    campaign.save()

    logger.info(f"Campaign {campaign.id} completed. Sent: {sent_count}, Failed: {failed_count}")

    return {"total": campaign.total_recipients, "sent": sent_count, "failed": failed_count}


def trigger_auto_send(trigger_type, subscription, context=None):
    """
    Automatically send SMS based on trigger type (e.g., on_subscribe, on_confirmation).

    Args:
        trigger_type (str): The trigger type ('on_subscribe', 'on_confirmation', etc.)
        subscription (SMSSubscription): The subscription object
        context (dict, optional): Variables to pass to the template

    Returns:
        tuple: (success: bool, log_object: SMSLog or None)
    """
    from shop.models import SMSTemplate

    if context is None:
        context = {}

    try:
        # Find active template with matching auto_trigger
        template = SMSTemplate.objects.filter(auto_trigger=trigger_type, is_active=True).first()

        if not template:
            logger.info(f"No active template found for trigger: {trigger_type}")
            return False, None

        # Send the message
        return send_from_template(
            phone_number=subscription.phone_number,
            template=template,
            context=context,
            subscription=subscription,
        )

    except Exception as e:
        logger.error(f"Error in auto-send for trigger {trigger_type}: {str(e)}")
        return False, None


def handle_opt_out(phone_number):
    """
    Handle opt-out request (e.g., customer texted STOP).

    Args:
        phone_number (str): The phone number that opted out

    Returns:
        bool: True if subscription was found and deactivated
    """
    from shop.models import SMSSubscription

    try:
        subscription = SMSSubscription.objects.get(phone_number=phone_number)
        subscription.is_active = False
        subscription.unsubscribed_at = timezone.now()
        subscription.save()

        logger.info(f"Opt-out processed for {phone_number}")
        return True

    except SMSSubscription.DoesNotExist:
        logger.warning(f"Opt-out request for unknown number: {phone_number}")
        return False


def handle_opt_in(phone_number):
    """
    Handle opt-in request (e.g., customer texted START).

    Args:
        phone_number (str): The phone number that opted in

    Returns:
        bool: True if subscription was found and reactivated
    """
    from shop.models import SMSSubscription

    try:
        subscription = SMSSubscription.objects.get(phone_number=phone_number)
        subscription.is_active = True
        subscription.unsubscribed_at = None
        subscription.save()

        logger.info(f"Opt-in processed for {phone_number}")
        return True

    except SMSSubscription.DoesNotExist:
        logger.info(f"Opt-in request for unknown number (no subscription): {phone_number}")
        return False
