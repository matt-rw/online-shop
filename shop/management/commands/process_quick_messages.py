"""
Management command to process scheduled quick messages.
Run this via cron or a task scheduler at regular intervals (e.g., every minute).

Usage:
    python manage.py process_quick_messages
"""

import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from shop.models import EmailSubscription, SMSSubscription
from shop.models.messaging import QuickMessage

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Process scheduled quick messages that are ready to be sent"

    def handle(self, *args, **options):
        now = timezone.now()

        # Find messages that are scheduled and past their scheduled time
        messages = QuickMessage.objects.filter(status="scheduled", scheduled_for__lte=now)

        if not messages.exists():
            self.stdout.write(self.style.SUCCESS("No scheduled messages ready to send"))
            return

        for message in messages:
            self.stdout.write(f"Processing scheduled message: {message.id} ({message.message_type})")

            try:
                # Mark as sending
                message.status = "sending"
                message.save(update_fields=["status"])

                sent_count = 0
                failed_count = 0

                if message.message_type == "email":
                    from shop.utils.email_helper import send_email

                    # Get active email subscribers
                    subscribers = EmailSubscription.objects.filter(is_active=True)
                    message.recipient_count = subscribers.count()
                    message.save(update_fields=["recipient_count"])

                    # Wrap content in basic HTML
                    html_body = f"<html><body><p>{message.content.replace(chr(10), '<br>')}</p></body></html>"

                    for sub in subscribers:
                        success, _ = send_email(
                            email_address=sub.email,
                            subject=message.subject,
                            html_body=html_body,
                            subscription=sub,
                            quick_message=message,
                        )
                        if success:
                            sent_count += 1
                        else:
                            failed_count += 1

                else:  # SMS
                    from shop.utils.twilio_helper import send_sms

                    # Get active SMS subscribers
                    subscribers = SMSSubscription.objects.filter(is_active=True)
                    message.recipient_count = subscribers.count()
                    message.save(update_fields=["recipient_count"])

                    for sub in subscribers:
                        success, _ = send_sms(
                            phone_number=sub.phone_number,
                            message=message.content,
                            subscription=sub,
                            quick_message=message,
                        )
                        if success:
                            sent_count += 1
                        else:
                            failed_count += 1

                # Update message with results
                message.sent_count = sent_count
                message.failed_count = failed_count
                message.status = "sent" if failed_count == 0 else ("partial" if sent_count > 0 else "failed")
                message.sent_at = timezone.now()
                message.save()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Message {message.id} completed. Sent: {sent_count}, Failed: {failed_count}"
                    )
                )

            except Exception as e:
                logger.error(f"Error processing message {message.id}: {str(e)}")
                message.status = "failed"
                message.save(update_fields=["status"])
                self.stdout.write(self.style.ERROR(f"Message {message.id} error: {str(e)}"))
