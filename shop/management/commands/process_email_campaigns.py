"""
Management command to process scheduled email campaigns.
Run this via cron or a task scheduler at regular intervals (e.g., every minute).

Usage:
    python manage.py process_email_campaigns
"""

import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from shop.models import EmailCampaign
from shop.utils.email_helper import send_campaign

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Process scheduled email campaigns that are ready to be sent"

    def handle(self, *args, **options):
        now = timezone.now()

        # Find campaigns that are scheduled and past their scheduled time
        campaigns = EmailCampaign.objects.filter(status="scheduled", scheduled_at__lte=now)

        if not campaigns.exists():
            self.stdout.write(self.style.SUCCESS("No campaigns ready to send"))
            return

        for campaign in campaigns:
            self.stdout.write(f"Processing campaign: {campaign.name}")

            try:
                result = send_campaign(campaign)

                if "error" in result:
                    self.stdout.write(
                        self.style.ERROR(f'Campaign {campaign.id} failed: {result["error"]}')
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Campaign {campaign.id} completed. "
                            f'Sent: {result["sent"]}, Failed: {result["failed"]}'
                        )
                    )

            except Exception as e:
                logger.error(f"Error processing campaign {campaign.id}: {str(e)}")
                self.stdout.write(self.style.ERROR(f"Campaign {campaign.id} error: {str(e)}"))
