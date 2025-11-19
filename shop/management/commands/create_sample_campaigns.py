from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from shop.models import Campaign, CampaignMessage
import random


class Command(BaseCommand):
    help = 'Create sample campaigns with messages for testing'

    def handle(self, *args, **options):
        # Clear existing test campaigns
        Campaign.objects.filter(name__startswith='Test Campaign').delete()

        today = timezone.now()

        # Campaign 1: Year-long multi-channel campaign
        campaign1 = Campaign.objects.create(
            name='Test Campaign - Annual Customer Journey',
            description='Full year campaign with diverse messaging across all channels',
            status='active',
            target_group='all_subscribers',
            active_from=today,
            active_until=today + timedelta(days=365)
        )

        annual_messages = [
            # Week 1 - Launch
            {'name': 'Welcome Email', 'days': 0, 'type': 'email'},
            {'name': 'Instagram Story', 'days': 1, 'type': 'instagram'},
            {'name': 'TikTok Teaser', 'days': 2, 'type': 'tiktok'},
            {'name': 'Follow-up SMS', 'days': 3, 'type': 'sms'},

            # Week 2 - Engagement
            {'name': 'Product Showcase Email', 'days': 7, 'type': 'email'},
            {'name': 'Snapchat Exclusive', 'days': 9, 'type': 'snapchat'},
            {'name': 'Instagram Reel', 'days': 10, 'type': 'instagram'},
            {'name': 'Flash Sale SMS', 'days': 12, 'type': 'sms'},
            {'name': 'TikTok Challenge', 'days': 14, 'type': 'tiktok'},

            # Month 1 - Conversion
            {'name': 'First Purchase Incentive', 'days': 21, 'type': 'email'},
            {'name': 'Limited Offer SMS', 'days': 25, 'type': 'sms'},
            {'name': 'Instagram Carousel', 'days': 28, 'type': 'instagram'},
            {'name': 'End of Month Newsletter', 'days': 30, 'type': 'email'},

            # Month 2 - Nurture
            {'name': 'Product Tips Email', 'days': 45, 'type': 'email'},
            {'name': 'TikTok Tutorial', 'days': 50, 'type': 'tiktok'},
            {'name': 'Customer Stories', 'days': 55, 'type': 'email'},
            {'name': 'Snapchat Behind Scenes', 'days': 60, 'type': 'snapchat'},

            # Quarter 1 Review
            {'name': 'Quarterly Newsletter', 'days': 90, 'type': 'email'},
            {'name': 'Instagram Highlights', 'days': 92, 'type': 'instagram'},
            {'name': 'Special Offer SMS', 'days': 95, 'type': 'sms'},

            # Mid-Year Campaign
            {'name': 'Summer Sale Email', 'days': 180, 'type': 'email'},
            {'name': 'TikTok Summer Vibes', 'days': 182, 'type': 'tiktok'},
            {'name': 'Instagram Summer Stories', 'days': 185, 'type': 'instagram'},
            {'name': 'SMS Flash Alert', 'days': 188, 'type': 'sms'},
            {'name': 'Snapchat Giveaway', 'days': 190, 'type': 'snapchat'},

            # Fall Campaign
            {'name': 'Fall Collection Email', 'days': 270, 'type': 'email'},
            {'name': 'Instagram Fall Lookbook', 'days': 272, 'type': 'instagram'},
            {'name': 'TikTok Trends', 'days': 275, 'type': 'tiktok'},

            # Year-End
            {'name': 'Year in Review Email', 'days': 350, 'type': 'email'},
            {'name': 'Thank You SMS', 'days': 355, 'type': 'sms'},
            {'name': 'Instagram Recap', 'days': 360, 'type': 'instagram'},
            {'name': 'Final Sale Email', 'days': 365, 'type': 'email'},
        ]

        for msg_data in annual_messages:
            CampaignMessage.objects.create(
                campaign=campaign1,
                name=msg_data['name'],
                message_type=msg_data['type'],
                trigger_type='specific_date',
                scheduled_date=today + timedelta(days=msg_data['days']),
                custom_subject=f"Subject: {msg_data['name']}",
                custom_content=f"This is a test message for {msg_data['name']}",
                status='scheduled' if msg_data['days'] > 0 else 'sent'
            )

        # Campaign 2: Heavy clustering test
        campaign2 = Campaign.objects.create(
            name='Test Campaign - Product Launch Blitz',
            description='Intense multi-day product launch with clustered messaging',
            status='active',
            target_group='all_subscribers',
            active_from=today,
            active_until=today + timedelta(days=14)
        )

        # Day 1 - Launch day (5 messages)
        launch_messages = [
            {'name': 'Launch Announcement Email', 'days': 1, 'type': 'email'},
            {'name': 'TikTok Launch Video', 'days': 1, 'type': 'tiktok'},
            {'name': 'Instagram Launch Post', 'days': 1, 'type': 'instagram'},
            {'name': 'SMS Launch Alert', 'days': 1, 'type': 'sms'},
            {'name': 'Snapchat Exclusive Preview', 'days': 1, 'type': 'snapchat'},

            # Day 2 - Follow up (4 messages)
            {'name': 'Still Available Email', 'days': 2, 'type': 'email'},
            {'name': 'Instagram Stories Update', 'days': 2, 'type': 'instagram'},
            {'name': 'TikTok User Reactions', 'days': 2, 'type': 'tiktok'},
            {'name': 'SMS Reminder', 'days': 2, 'type': 'sms'},

            # Day 7 - Mid-campaign (3 messages)
            {'name': 'Week 1 Recap', 'days': 7, 'type': 'email'},
            {'name': 'Instagram Carousel', 'days': 7, 'type': 'instagram'},
            {'name': 'TikTok Testimonials', 'days': 7, 'type': 'tiktok'},

            # Day 14 - Final push (4 messages)
            {'name': 'Last Chance Email', 'days': 14, 'type': 'email'},
            {'name': 'Final Hours SMS', 'days': 14, 'type': 'sms'},
            {'name': 'Instagram Countdown', 'days': 14, 'type': 'instagram'},
            {'name': 'TikTok Finale', 'days': 14, 'type': 'tiktok'},
        ]

        for msg_data in launch_messages:
            CampaignMessage.objects.create(
                campaign=campaign2,
                name=msg_data['name'],
                message_type=msg_data['type'],
                trigger_type='specific_date',
                scheduled_date=today + timedelta(days=msg_data['days']),
                custom_subject=f"Subject: {msg_data['name']}",
                custom_content=f"This is a test message for {msg_data['name']}",
                status='scheduled'
            )

        # Campaign 3: Seasonal campaign
        campaign3 = Campaign.objects.create(
            name='Test Campaign - Holiday Season',
            description='6-month holiday campaign with mixed channels',
            status='active',
            target_group='all_subscribers',
            active_from=today,
            active_until=today + timedelta(days=180)
        )

        holiday_messages = [
            {'name': 'Holiday Preview Email', 'days': 5, 'type': 'email'},
            {'name': 'Instagram Gift Guide', 'days': 15, 'type': 'instagram'},
            {'name': 'TikTok Holiday Ideas', 'days': 25, 'type': 'tiktok'},
            {'name': 'Early Bird SMS', 'days': 30, 'type': 'sms'},
            {'name': 'Snapchat Countdown', 'days': 40, 'type': 'snapchat'},
            {'name': 'Mid-Season Sale Email', 'days': 60, 'type': 'email'},
            {'name': 'Instagram Flash Sale', 'days': 75, 'type': 'instagram'},
            {'name': 'TikTok Unboxing', 'days': 90, 'type': 'tiktok'},
            {'name': 'Extended Sale Email', 'days': 120, 'type': 'email'},
            {'name': 'Final Days SMS', 'days': 150, 'type': 'sms'},
            {'name': 'Thank You Email', 'days': 180, 'type': 'email'},
        ]

        for msg_data in holiday_messages:
            CampaignMessage.objects.create(
                campaign=campaign3,
                name=msg_data['name'],
                message_type=msg_data['type'],
                trigger_type='specific_date',
                scheduled_date=today + timedelta(days=msg_data['days']),
                custom_subject=f"Subject: {msg_data['name']}",
                custom_content=f"This is a test message for {msg_data['name']}",
                status='scheduled'
            )

        # Campaign 4: Weekly newsletter campaign
        campaign4 = Campaign.objects.create(
            name='Test Campaign - Weekly Newsletter',
            description='Regular weekly touchpoints with subscribers',
            status='active',
            target_group='email_subscribers',
            active_from=today,
            active_until=today + timedelta(days=90)
        )

        newsletter_messages = [
            {'name': 'Week 1 Newsletter', 'days': 0, 'type': 'email'},
            {'name': 'Week 2 Newsletter', 'days': 7, 'type': 'email'},
            {'name': 'Week 3 Newsletter', 'days': 14, 'type': 'email'},
            {'name': 'Week 4 Newsletter', 'days': 21, 'type': 'email'},
            {'name': 'Week 5 Newsletter', 'days': 28, 'type': 'email'},
            {'name': 'Week 6 Newsletter', 'days': 35, 'type': 'email'},
            {'name': 'Week 7 Newsletter', 'days': 42, 'type': 'email'},
            {'name': 'Week 8 Newsletter', 'days': 49, 'type': 'email'},
            {'name': 'Week 9 Newsletter', 'days': 56, 'type': 'email'},
            {'name': 'Week 10 Newsletter', 'days': 63, 'type': 'email'},
            {'name': 'Week 11 Newsletter', 'days': 70, 'type': 'email'},
            {'name': 'Week 12 Newsletter', 'days': 77, 'type': 'email'},
            {'name': 'Week 13 Newsletter', 'days': 84, 'type': 'email'},
        ]

        for msg_data in newsletter_messages:
            CampaignMessage.objects.create(
                campaign=campaign4,
                name=msg_data['name'],
                message_type=msg_data['type'],
                trigger_type='specific_date',
                scheduled_date=today + timedelta(days=msg_data['days']),
                custom_subject=f"Subject: {msg_data['name']}",
                custom_content=f"This is a test message for {msg_data['name']}",
                status='scheduled' if msg_data['days'] > 0 else 'sent'
            )

        # Campaign 5: Flash sale - super dense clustering
        campaign5 = Campaign.objects.create(
            name='Test Campaign - 24hr Flash Sale',
            description='Aggressive flash sale with maximum message density',
            status='active',
            target_group='all_subscribers',
            active_from=today,
            active_until=today + timedelta(days=3)
        )

        flash_messages = [
            # Day 1 - 8 messages on same day
            {'name': 'Flash Sale Announcement', 'days': 1, 'type': 'email'},
            {'name': 'TikTok Flash Teaser', 'days': 1, 'type': 'tiktok'},
            {'name': 'Instagram Flash Story 1', 'days': 1, 'type': 'instagram'},
            {'name': 'SMS Flash Alert 1', 'days': 1, 'type': 'sms'},
            {'name': 'Snapchat Flash', 'days': 1, 'type': 'snapchat'},
            {'name': 'Instagram Flash Story 2', 'days': 1, 'type': 'instagram'},
            {'name': 'Email Reminder 1', 'days': 1, 'type': 'email'},
            {'name': 'SMS Flash Alert 2', 'days': 1, 'type': 'sms'},

            # Day 2 - 6 messages
            {'name': 'Midnight Update', 'days': 2, 'type': 'email'},
            {'name': 'TikTok Update', 'days': 2, 'type': 'tiktok'},
            {'name': 'Instagram Update', 'days': 2, 'type': 'instagram'},
            {'name': 'SMS Update', 'days': 2, 'type': 'sms'},
            {'name': 'Email Final Hours', 'days': 2, 'type': 'email'},
            {'name': 'SMS Final Call', 'days': 2, 'type': 'sms'},

            # Day 3 - Last push
            {'name': 'Sale Ending Email', 'days': 3, 'type': 'email'},
            {'name': 'Instagram Countdown', 'days': 3, 'type': 'instagram'},
            {'name': 'TikTok Last Chance', 'days': 3, 'type': 'tiktok'},
        ]

        for msg_data in flash_messages:
            CampaignMessage.objects.create(
                campaign=campaign5,
                name=msg_data['name'],
                message_type=msg_data['type'],
                trigger_type='specific_date',
                scheduled_date=today + timedelta(days=msg_data['days']),
                custom_subject=f"Subject: {msg_data['name']}",
                custom_content=f"This is a test message for {msg_data['name']}",
                status='scheduled'
            )

        # Campaign 6: New customer onboarding
        campaign6 = Campaign.objects.create(
            name='Test Campaign - New Customer Onboarding',
            description='30-day onboarding journey for new customers',
            status='active',
            target_group='all_subscribers',
            active_from=today,
            active_until=today + timedelta(days=30)
        )

        onboarding_messages = [
            {'name': 'Welcome Email', 'days': 0, 'type': 'email'},
            {'name': 'Follow Instagram', 'days': 1, 'type': 'instagram'},
            {'name': 'Product Guide Email', 'days': 3, 'type': 'email'},
            {'name': 'First Purchase Discount SMS', 'days': 5, 'type': 'sms'},
            {'name': 'TikTok How-To', 'days': 7, 'type': 'tiktok'},
            {'name': 'Week 2 Check-in Email', 'days': 14, 'type': 'email'},
            {'name': 'Instagram Community Invite', 'days': 16, 'type': 'instagram'},
            {'name': 'Special Offer SMS', 'days': 20, 'type': 'sms'},
            {'name': 'Customer Success Story', 'days': 25, 'type': 'email'},
            {'name': 'Month 1 Celebration', 'days': 30, 'type': 'email'},
        ]

        for msg_data in onboarding_messages:
            CampaignMessage.objects.create(
                campaign=campaign6,
                name=msg_data['name'],
                message_type=msg_data['type'],
                trigger_type='specific_date',
                scheduled_date=today + timedelta(days=msg_data['days']),
                custom_subject=f"Subject: {msg_data['name']}",
                custom_content=f"This is a test message for {msg_data['name']}",
                status='scheduled' if msg_data['days'] > 0 else 'sent'
            )

        # Campaign 7: Re-engagement campaign
        campaign7 = Campaign.objects.create(
            name='Test Campaign - Win-Back Inactive Users',
            description='Re-engage users who haven\'t purchased in 60 days',
            status='active',
            target_group='all_subscribers',
            active_from=today,
            active_until=today + timedelta(days=45)
        )

        winback_messages = [
            {'name': 'We Miss You Email', 'days': 2, 'type': 'email'},
            {'name': 'Exclusive Comeback Offer', 'days': 7, 'type': 'email'},
            {'name': 'Instagram New Arrivals', 'days': 10, 'type': 'instagram'},
            {'name': 'SMS Special Discount', 'days': 14, 'type': 'sms'},
            {'name': 'TikTok What\'s New', 'days': 18, 'type': 'tiktok'},
            {'name': 'Personalized Recommendations', 'days': 25, 'type': 'email'},
            {'name': 'Last Chance Offer', 'days': 35, 'type': 'email'},
            {'name': 'Final SMS Reminder', 'days': 40, 'type': 'sms'},
        ]

        for msg_data in winback_messages:
            CampaignMessage.objects.create(
                campaign=campaign7,
                name=msg_data['name'],
                message_type=msg_data['type'],
                trigger_type='specific_date',
                scheduled_date=today + timedelta(days=msg_data['days']),
                custom_subject=f"Subject: {msg_data['name']}",
                custom_content=f"This is a test message for {msg_data['name']}",
                status='scheduled'
            )

        # Campaign 8: VIP exclusive campaign
        campaign8 = Campaign.objects.create(
            name='Test Campaign - VIP Exclusive Access',
            description='Premium content and early access for VIP customers',
            status='active',
            target_group='all_subscribers',
            active_from=today,
            active_until=today + timedelta(days=60)
        )

        vip_messages = [
            {'name': 'VIP Welcome Email', 'days': 1, 'type': 'email'},
            {'name': 'Early Access Preview', 'days': 5, 'type': 'email'},
            {'name': 'Instagram VIP Lounge', 'days': 8, 'type': 'instagram'},
            {'name': 'SMS Exclusive Drop Alert', 'days': 12, 'type': 'sms'},
            {'name': 'TikTok VIP Behind Scenes', 'days': 15, 'type': 'tiktok'},
            {'name': 'Private Sale Email', 'days': 20, 'type': 'email'},
            {'name': 'Snapchat VIP Event', 'days': 25, 'type': 'snapchat'},
            {'name': 'Mid-Month VIP Newsletter', 'days': 30, 'type': 'email'},
            {'name': 'Instagram VIP Styling', 'days': 35, 'type': 'instagram'},
            {'name': 'SMS VIP Flash Sale', 'days': 40, 'type': 'sms'},
            {'name': 'VIP Member Appreciation', 'days': 50, 'type': 'email'},
            {'name': 'End of Period Thank You', 'days': 60, 'type': 'email'},
        ]

        for msg_data in vip_messages:
            CampaignMessage.objects.create(
                campaign=campaign8,
                name=msg_data['name'],
                message_type=msg_data['type'],
                trigger_type='specific_date',
                scheduled_date=today + timedelta(days=msg_data['days']),
                custom_subject=f"Subject: {msg_data['name']}",
                custom_content=f"This is a test message for {msg_data['name']}",
                status='scheduled'
            )

        total_messages = (len(annual_messages) + len(launch_messages) + len(holiday_messages) +
                         len(newsletter_messages) + len(flash_messages) + len(onboarding_messages) +
                         len(winback_messages) + len(vip_messages))

        self.stdout.write(self.style.SUCCESS(
            f'Successfully created 8 test campaigns with {total_messages} messages across all channels'
        ))
