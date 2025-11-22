"""
Django management command to manually process scheduled campaigns.
For development/testing use.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Processes all scheduled email and SMS campaigns that are ready to send'

    def handle(self, *args, **options):
        from shop.models import EmailCampaign, SMSCampaign
        from shop.utils.email_helper import send_campaign as send_email_campaign
        from shop.utils.twilio_helper import send_campaign as send_sms_campaign

        now = timezone.now()

        self.stdout.write(self.style.SUCCESS(f'\n=== Processing Campaigns at {now} ===\n'))

        # Process email campaigns
        email_campaigns = EmailCampaign.objects.filter(
            status='scheduled',
            scheduled_at__lte=now
        )

        email_count = email_campaigns.count()
        self.stdout.write(f'Found {email_count} email campaign(s) ready to send')

        email_sent = 0
        email_failed = 0

        for campaign in email_campaigns:
            self.stdout.write(f'\nProcessing email campaign: {campaign.name}')
            try:
                result = send_email_campaign(campaign)
                if 'error' in result:
                    email_failed += 1
                    self.stdout.write(self.style.ERROR(f'  ✗ Failed: {result["error"]}'))
                else:
                    sent = result.get('sent', 0)
                    failed = result.get('failed', 0)
                    email_sent += sent
                    email_failed += failed
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Sent: {sent}, Failed: {failed}'))
            except Exception as e:
                email_failed += 1
                self.stdout.write(self.style.ERROR(f'  ✗ Error: {str(e)}'))

        # Process SMS campaigns
        sms_campaigns = SMSCampaign.objects.filter(
            status='scheduled',
            scheduled_at__lte=now
        )

        sms_count = sms_campaigns.count()
        self.stdout.write(f'\nFound {sms_count} SMS campaign(s) ready to send')

        sms_sent = 0
        sms_failed = 0

        for campaign in sms_campaigns:
            self.stdout.write(f'\nProcessing SMS campaign: {campaign.name}')
            try:
                result = send_sms_campaign(campaign)
                if 'error' in result:
                    sms_failed += 1
                    self.stdout.write(self.style.ERROR(f'  ✗ Failed: {result["error"]}'))
                else:
                    sent = result.get('sent', 0)
                    failed = result.get('failed', 0)
                    sms_sent += sent
                    sms_failed += failed
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Sent: {sent}, Failed: {failed}'))
            except Exception as e:
                sms_failed += 1
                self.stdout.write(self.style.ERROR(f'  ✗ Error: {str(e)}'))

        # Summary
        self.stdout.write(self.style.SUCCESS('\n=== Summary ==='))
        self.stdout.write(f'Email: {email_sent} sent, {email_failed} failed')
        self.stdout.write(f'SMS: {sms_sent} sent, {sms_failed} failed')
        self.stdout.write(self.style.SUCCESS('\nDone!\n'))
