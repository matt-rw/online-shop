import atexit
import logging
import os

from django.apps import AppConfig

logger = logging.getLogger(__name__)

# Global scheduler reference for cleanup
_scheduler = None


class ShopConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "shop"

    def ready(self):
        """Import signal handlers when app is ready."""
        import shop.signals

        # Start scheduler for processing campaigns and quick messages
        # Runs in DEBUG mode automatically, or in production when ENABLE_SCHEDULER=true
        from django.conf import settings

        # Check if we should start the scheduler
        enable_scheduler = os.environ.get('ENABLE_SCHEDULER', '').lower() == 'true'

        # For production: only start on first worker (use SCHEDULER_ENABLED file lock)
        # For development: only start on main process (RUN_MAIN=true)
        should_start = False

        if settings.DEBUG:
            # Development: Django reloader sets RUN_MAIN=true on the actual server process
            should_start = os.environ.get('RUN_MAIN') == 'true'
        elif enable_scheduler:
            # Production: Use file-based lock to ensure only one scheduler runs
            should_start = self._acquire_scheduler_lock()

        if should_start:
            self._start_scheduler()

    def _acquire_scheduler_lock(self):
        """Try to acquire a lock to be the scheduler process. Returns True if acquired."""
        import tempfile
        import fcntl

        lock_file = os.path.join(tempfile.gettempdir(), 'django_scheduler.lock')

        try:
            # Open or create lock file
            self._lock_fd = open(lock_file, 'w')
            # Try to acquire exclusive lock (non-blocking)
            fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Write our PID
            self._lock_fd.write(str(os.getpid()))
            self._lock_fd.flush()
            logger.info(f'Acquired scheduler lock (PID: {os.getpid()})')
            return True
        except (IOError, OSError):
            # Another process has the lock
            logger.info('Another process is running the scheduler')
            return False

    def _start_scheduler(self):
        """Start background scheduler for automatic message processing."""
        global _scheduler

        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger

        _scheduler = BackgroundScheduler()

        _scheduler.add_job(
            self._process_scheduled_items,
            trigger=IntervalTrigger(minutes=1),
            id='process_scheduled_items',
            name='Process scheduled campaigns and messages',
            replace_existing=True,
            max_instances=1,  # Prevent overlapping runs
            coalesce=True,  # Combine missed runs into one
        )

        _scheduler.start()
        logger.info('Message scheduler started - checking every minute for scheduled items')

        # Register shutdown handler
        atexit.register(self._shutdown_scheduler)

    @staticmethod
    def _shutdown_scheduler():
        """Gracefully shutdown the scheduler."""
        global _scheduler
        if _scheduler and _scheduler.running:
            logger.info('Shutting down message scheduler...')
            _scheduler.shutdown(wait=False)

    @staticmethod
    def _process_scheduled_items():
        """Process all scheduled campaigns and quick messages."""
        from django.db import close_old_connections
        from django.utils import timezone
        from shop.models import EmailCampaign, SMSCampaign
        from shop.utils.email_helper import send_campaign as send_email_campaign
        from shop.utils.twilio_helper import send_campaign as send_sms_campaign

        # Ensure fresh database connection (important for long-running processes)
        close_old_connections()

        now = timezone.now()

        # Process email campaigns
        email_campaigns = EmailCampaign.objects.filter(
            status='scheduled',
            scheduled_at__lte=now
        )

        for campaign in email_campaigns:
            try:
                send_email_campaign(campaign)
                logger.info(f'Processed email campaign: {campaign.name}')
            except Exception as e:
                logger.error(f'Error processing email campaign {campaign.id}: {str(e)}')

        # Process SMS campaigns
        sms_campaigns = SMSCampaign.objects.filter(
            status='scheduled',
            scheduled_at__lte=now
        )

        for campaign in sms_campaigns:
            try:
                send_sms_campaign(campaign)
                logger.info(f'Processed SMS campaign: {campaign.name}')
            except Exception as e:
                logger.error(f'Error processing SMS campaign {campaign.id}: {str(e)}')

        # Process quick messages
        ShopConfig._process_quick_messages(now)

    @staticmethod
    def _process_quick_messages(now):
        """Process scheduled quick messages that are ready to be sent."""
        import time
        from django.db import transaction
        from django.db.models import F
        from shop.models import EmailSubscription, SMSSubscription
        from shop.models.messaging import QuickMessage

        # Use select_for_update to prevent race conditions
        # Only pick up messages that are still in 'scheduled' status
        with transaction.atomic():
            # Lock and fetch messages that need processing
            messages = list(
                QuickMessage.objects.select_for_update(skip_locked=True)
                .filter(status="scheduled", scheduled_for__lte=now)
                [:10]  # Process max 10 at a time to avoid long locks
            )

            # Mark them as sending immediately to prevent other workers from picking them up
            for message in messages:
                message.status = "sending"
                message.save(update_fields=["status"])

        # Now process each message outside the lock
        for message in messages:
            try:
                sent_count = 0
                failed_count = 0

                if message.message_type == "email":
                    from shop.utils.email_helper import send_email

                    # Get count first (lightweight query)
                    recipient_count = EmailSubscription.objects.filter(is_active=True).count()
                    message.recipient_count = recipient_count
                    message.save(update_fields=["recipient_count"])

                    # Wrap content in basic HTML
                    html_body = f"<html><body><p>{message.content.replace(chr(10), '<br>')}</p></body></html>"

                    # Process in batches to avoid memory issues
                    batch_size = 100
                    for offset in range(0, recipient_count, batch_size):
                        subscribers = EmailSubscription.objects.filter(is_active=True)[offset:offset + batch_size]

                        for sub in subscribers:
                            try:
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
                            except Exception as e:
                                logger.error(f"Error sending email to {sub.email}: {str(e)}")
                                failed_count += 1

                            # Small delay to avoid rate limiting (50ms between sends)
                            time.sleep(0.05)

                else:  # SMS
                    from shop.utils.twilio_helper import send_sms

                    # Get count first
                    recipient_count = SMSSubscription.objects.filter(is_active=True).count()
                    message.recipient_count = recipient_count
                    message.save(update_fields=["recipient_count"])

                    # Process in batches
                    batch_size = 100
                    for offset in range(0, recipient_count, batch_size):
                        subscribers = SMSSubscription.objects.filter(is_active=True)[offset:offset + batch_size]

                        for sub in subscribers:
                            try:
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
                            except Exception as e:
                                logger.error(f"Error sending SMS to {sub.phone_number}: {str(e)}")
                                failed_count += 1

                            # Twilio rate limit: ~1 msg/sec for trial, higher for paid
                            time.sleep(0.1)

                # Update message with results
                from django.utils import timezone as tz
                message.sent_count = sent_count
                message.failed_count = failed_count
                message.status = "sent" if failed_count == 0 else ("partial" if sent_count > 0 else "failed")
                message.sent_at = tz.now()
                message.save()

                logger.info(f'Processed quick message {message.id}: sent={sent_count}, failed={failed_count}')

            except Exception as e:
                logger.exception(f"Error processing quick message {message.id}: {str(e)}")
                try:
                    message.status = "failed"
                    message.save(update_fields=["status"])
                except Exception:
                    pass  # Don't fail if we can't update status
