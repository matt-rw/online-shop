import logging
import os

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class ShopConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "shop"

    def ready(self):
        """Import signal handlers when app is ready."""
        import shop.signals

        # Start campaign scheduler in DEBUG mode only
        # This allows automatic campaign processing during development
        # In production, use the webhook + external cron service instead
        if os.environ.get('RUN_MAIN') == 'true' or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            # Only run in the main process (not the reloader)
            from django.conf import settings
            if settings.DEBUG:
                self._start_campaign_scheduler()

    def _start_campaign_scheduler(self):
        """Start background scheduler for automatic campaign processing in DEBUG mode."""
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        from django.utils import timezone

        scheduler = BackgroundScheduler()

        scheduler.add_job(
            self._process_campaigns,
            trigger=IntervalTrigger(minutes=1),
            id='process_campaigns',
            name='Process scheduled campaigns',
            replace_existing=True
        )

        scheduler.start()
        logger.info('Campaign scheduler started (DEBUG mode) - campaigns will process every minute')

    @staticmethod
    def _process_campaigns():
        """Process all scheduled campaigns (both email and SMS)."""
        from django.utils import timezone
        from shop.models import EmailCampaign, SMSCampaign
        from shop.utils.email_helper import send_campaign as send_email_campaign
        from shop.utils.twilio_helper import send_campaign as send_sms_campaign

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
