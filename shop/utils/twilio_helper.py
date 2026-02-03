import logging

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def send_sms(phone_number, message, subscription=None, campaign=None, template=None, quick_message=None):
    """
    Send an SMS message using Twilio and log the result.

    Args:
        phone_number (str): The recipient's phone number in E.164 format (e.g., +1234567890)
        message (str): The message body to send
        subscription (SMSSubscription, optional): The subscription object if available
        campaign (SMSCampaign, optional): The campaign this SMS belongs to
        template (SMSTemplate, optional): The template used for this SMS

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

    # Check if Twilio is configured
    if not all(
        [settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, settings.TWILIO_PHONE_NUMBER]
    ):
        logger.warning("Twilio credentials not configured. SMS not sent.")
        log.status = "failed"
        log.error_message = "Twilio not configured"
        log.save()
        return False, log

    try:
        from twilio.rest import Client

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

        message_obj = client.messages.create(
            body=message, from_=settings.TWILIO_PHONE_NUMBER, to=phone_number
        )

        # Update log with success
        log.status = "sent"
        log.twilio_sid = message_obj.sid
        log.save()

        logger.info(f"SMS sent successfully to {phone_number}. SID: {message_obj.sid}")

        # Update template usage count if template was used
        if template:
            template.times_used += 1
            template.save()

        return True, log

    except Exception as e:
        logger.error(f"Failed to send SMS to {phone_number}: {str(e)}")
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

    # Get recipients
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
