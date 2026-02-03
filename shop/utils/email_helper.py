import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def send_email(
    email_address,
    subject,
    html_body,
    text_body=None,
    subscription=None,
    campaign=None,
    template=None,
    quick_message=None,
):
    """
    Send an email and log the result.

    Args:
        email_address (str): The recipient's email address
        subject (str): Email subject line
        html_body (str): HTML email body
        text_body (str, optional): Plain text email body (auto-generated if not provided)
        subscription (EmailSubscription, optional): The subscription object if available
        campaign (EmailCampaign, optional): The campaign this email belongs to
        template (EmailTemplate, optional): The template used for this email

    Returns:
        tuple: (success: bool, log_object: EmailLog)
    """
    from shop.models import EmailLog

    # Auto-generate text body from HTML if not provided
    if not text_body:
        text_body = strip_tags(html_body)

    # Create log entry
    log = EmailLog.objects.create(
        subscription=subscription,
        email_address=email_address,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        campaign=campaign,
        template=template,
        quick_message=quick_message,
        status="queued",
    )

    try:
        # Create email message
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email_address],
        )
        email.attach_alternative(html_body, "text/html")

        # Send email
        email.send(fail_silently=False)

        # Update log with success
        log.status = "sent"
        log.save()

        logger.info(f"Email sent successfully to {email_address}")

        # Update template usage count if template was used
        if template:
            template.times_used += 1
            template.save()

        return True, log

    except Exception as e:
        logger.error(f"Failed to send email to {email_address}: {str(e)}")
        log.status = "failed"
        log.error_message = str(e)
        log.save()
        return False, log


def send_from_template(email_address, template, context=None, subscription=None, campaign=None):
    """
    Send an email using a template.

    Args:
        email_address (str): The recipient's email address
        template (EmailTemplate): The template to use
        context (dict, optional): Variables to render in the template
        subscription (EmailSubscription, optional): The subscription object
        campaign (EmailCampaign, optional): The campaign this belongs to

    Returns:
        tuple: (success: bool, log_object: EmailLog)
    """
    if context is None:
        context = {}

    # Render the template
    subject, html_body, text_body = template.render(**context)

    # Send the email
    return send_email(
        email_address=email_address,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        subscription=subscription,
        campaign=campaign,
        template=template,
    )


def send_campaign(campaign):
    """
    Send an email campaign to all targeted subscribers.

    Args:
        campaign (EmailCampaign): The campaign to send

    Returns:
        dict: Statistics about the send (total, sent, failed)
    """
    from shop.models import EmailSubscription

    if campaign.status not in ["draft", "scheduled"]:
        logger.warning(f"Cannot send campaign {campaign.id} with status {campaign.status}")
        return {"error": "Invalid campaign status"}

    # Update campaign status
    campaign.status = "sending"
    campaign.started_at = timezone.now()
    campaign.save()

    # Get recipients
    if campaign.send_to_all_active:
        recipients = EmailSubscription.objects.filter(is_active=True, is_confirmed=True)
    else:
        recipients = EmailSubscription.objects.none()

    campaign.total_recipients = recipients.count()
    campaign.save()

    sent_count = 0
    failed_count = 0

    # Send to each recipient
    for subscription in recipients:
        success, log = send_from_template(
            email_address=subscription.email,
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
    Automatically send email based on trigger type (e.g., on_subscribe, on_confirmation).

    Args:
        trigger_type (str): The trigger type ('on_subscribe', 'on_confirmation', etc.)
        subscription (EmailSubscription): The subscription object
        context (dict, optional): Variables to pass to the template

    Returns:
        tuple: (success: bool, log_object: EmailLog or None)
    """
    from shop.models import EmailTemplate

    if context is None:
        context = {}

    try:
        # Find active template with matching auto_trigger
        template = EmailTemplate.objects.filter(auto_trigger=trigger_type, is_active=True).first()

        if not template:
            logger.info(f"No active template found for trigger: {trigger_type}")
            return False, None

        # Send the message
        return send_from_template(
            email_address=subscription.email,
            template=template,
            context=context,
            subscription=subscription,
        )

    except Exception as e:
        logger.error(f"Error in auto-send for trigger {trigger_type}: {str(e)}")
        return False, None
