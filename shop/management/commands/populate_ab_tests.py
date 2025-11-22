"""
Management command to populate A/B testing example data.
"""

from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from shop.models.campaign import Campaign, CampaignMessage
from shop.models.product import Discount


class Command(BaseCommand):
    help = "Populate database with example A/B testing data"

    def handle(self, *args, **options):
        self.stdout.write("Creating A/B testing example data...")

        # Create Instagram Campaign with A/B tests
        instagram_campaign = Campaign.objects.create(
            name="Spring Sale Instagram Campaign",
            description="Testing emoji vs plain text captions on Instagram",
            status="active",
            active_from=timezone.now() - timedelta(days=7),
        )

        # Instagram A/B Test: Emoji vs Plain Text
        CampaignMessage.objects.create(
            campaign=instagram_campaign,
            name="Instagram Post - With Emoji",
            message_type="instagram",
            custom_subject="Spring Sale Post A",
            custom_content="🌸 Spring is here! Get 20% off all new arrivals 🛍️ Limited time only!",
            variant_name="A",
            test_tags="emoji,casual,urgency",
            landing_url="http://localhost:8000/shop/new-arrivals/",
            utm_source="instagram",
            utm_medium="social",
            utm_campaign="spring_sale",
            utm_content="emoji_variant",
            status="sent",
            total_recipients=500,
            clicks=85,
            conversions=12,
            revenue=Decimal("480.00"),
        )

        CampaignMessage.objects.create(
            campaign=instagram_campaign,
            name="Instagram Post - Plain Text",
            message_type="instagram",
            custom_subject="Spring Sale Post B",
            custom_content="Spring is here! Get 20% off all new arrivals. Limited time only!",
            variant_name="B",
            test_tags="professional,minimal,urgency",
            landing_url="http://localhost:8000/shop/new-arrivals/",
            utm_source="instagram",
            utm_medium="social",
            utm_campaign="spring_sale",
            utm_content="plain_variant",
            status="sent",
            total_recipients=500,
            clicks=52,
            conversions=6,
            revenue=Decimal("240.00"),
        )

        self.stdout.write(self.style.SUCCESS("✓ Created Instagram A/B test (Emoji vs Plain)"))

        # Create TikTok Campaign with A/B tests
        tiktok_campaign = Campaign.objects.create(
            name="Flash Sale TikTok Campaign",
            description="Testing urgency vs scarcity messaging on TikTok",
            status="active",
            active_from=timezone.now() - timedelta(days=5),
        )

        # TikTok A/B Test: Urgency vs Scarcity messaging
        CampaignMessage.objects.create(
            campaign=tiktok_campaign,
            name="TikTok - Urgency Messaging",
            message_type="tiktok",
            custom_subject="Flash Sale - Urgency",
            custom_content="⏰ ONLY 3 HOURS LEFT! Flash sale ending soon - don't miss out!",
            variant_name="A",
            test_tags="urgency,emoji,direct",
            landing_url="http://localhost:8000/shop/sale/",
            utm_source="tiktok",
            utm_medium="social",
            utm_campaign="flash_sale",
            utm_content="urgency",
            status="sent",
            total_recipients=1000,
            clicks=180,
            conversions=28,
            revenue=Decimal("1120.00"),
        )

        CampaignMessage.objects.create(
            campaign=tiktok_campaign,
            name="TikTok - Scarcity Messaging",
            message_type="tiktok",
            custom_subject="Flash Sale - Scarcity",
            custom_content="🔥 Only 15 items left in stock! Once they're gone, they're GONE!",
            variant_name="B",
            test_tags="scarcity,emoji,direct",
            landing_url="http://localhost:8000/shop/sale/",
            utm_source="tiktok",
            utm_medium="social",
            utm_campaign="flash_sale",
            utm_content="scarcity",
            status="sent",
            total_recipients=1000,
            clicks=245,
            conversions=42,
            revenue=Decimal("1680.00"),
        )

        self.stdout.write(self.style.SUCCESS("✓ Created TikTok A/B test (Urgency vs Scarcity)"))

        # Create Email Campaign with A/B tests
        email_campaign = Campaign.objects.create(
            name="Summer Newsletter",
            description="Testing short vs long email subject lines",
            status="active",
            active_from=timezone.now() - timedelta(days=3),
        )

        # Email A/B Test: Short vs Long subject line
        CampaignMessage.objects.create(
            campaign=email_campaign,
            name="Email - Short Subject",
            message_type="email",
            custom_subject="Your summer favorites are back",
            custom_content="Check out our summer collection...",
            variant_name="A",
            test_tags="short,casual",
            landing_url="http://localhost:8000/shop/",
            utm_source="email",
            utm_medium="email",
            utm_campaign="summer_newsletter",
            utm_content="short_subject",
            status="sent",
            total_recipients=2000,
            clicks=320,
            conversions=45,
            revenue=Decimal("1800.00"),
        )

        CampaignMessage.objects.create(
            campaign=email_campaign,
            name="Email - Long Subject",
            message_type="email",
            custom_subject="The summer styles you loved are back in stock - shop now before they're gone!",
            custom_content="Check out our summer collection...",
            variant_name="B",
            test_tags="long,urgency,value",
            landing_url="http://localhost:8000/shop/",
            utm_source="email",
            utm_medium="email",
            utm_campaign="summer_newsletter",
            utm_content="long_subject",
            status="sent",
            total_recipients=2000,
            clicks=280,
            conversions=38,
            revenue=Decimal("1520.00"),
        )

        self.stdout.write(self.style.SUCCESS("✓ Created Email A/B test (Short vs Long subject)"))

        # Create Discount Code A/B Tests
        now = timezone.now()

        # Discount A/B Test: 20% vs 30% off
        Discount.objects.get_or_create(
            code="SPRING20AB",
            defaults={
                "name": "Spring Sale - 20% Off",
                "discount_type": "percentage",
                "value": Decimal("20.00"),
                "variant_name": "A",
                "test_tags": "discount,percentage,moderate",
                "landing_url": "http://localhost:8000/shop/sale/",
                "utm_source": "instagram",
                "utm_medium": "social",
                "utm_campaign": "spring_discount",
                "valid_from": now - timedelta(days=10),
                "valid_until": now + timedelta(days=20),
                "is_active": True,
                "times_used": 145,
            }
        )

        Discount.objects.get_or_create(
            code="SPRING30AB",
            defaults={
                "name": "Spring Sale - 30% Off",
                "discount_type": "percentage",
                "value": Decimal("30.00"),
                "variant_name": "B",
                "test_tags": "discount,percentage,aggressive",
                "landing_url": "http://localhost:8000/shop/sale/",
                "utm_source": "instagram",
                "utm_medium": "social",
                "utm_campaign": "spring_discount",
                "valid_from": now - timedelta(days=10),
                "valid_until": now + timedelta(days=20),
                "is_active": True,
                "times_used": 98,
            }
        )

        self.stdout.write(self.style.SUCCESS("✓ Created Discount A/B test (20% vs 30%)"))

        # Discount A/B Test: Free Shipping vs $10 Off
        Discount.objects.get_or_create(
            code="FREESHIP2025",
            defaults={
                "name": "New Customer - Free Shipping",
                "discount_type": "free_shipping",
                "value": Decimal("0.00"),
                "variant_name": "A",
                "test_tags": "freeship,value,newcustomer",
                "landing_url": "http://localhost:8000/",
                "utm_source": "email",
                "utm_medium": "email",
                "utm_campaign": "welcome_offer",
                "valid_from": now - timedelta(days=5),
                "valid_until": now + timedelta(days=25),
                "is_active": True,
                "times_used": 67,
            }
        )

        Discount.objects.get_or_create(
            code="WELCOME2025",
            defaults={
                "name": "New Customer - $10 Off",
                "discount_type": "fixed",
                "value": Decimal("10.00"),
                "variant_name": "B",
                "test_tags": "discount,fixed,newcustomer",
                "landing_url": "http://localhost:8000/",
                "utm_source": "email",
                "utm_medium": "email",
                "utm_campaign": "welcome_offer",
                "valid_from": now - timedelta(days=5),
                "valid_until": now + timedelta(days=25),
                "is_active": True,
                "times_used": 89,
            }
        )

        self.stdout.write(self.style.SUCCESS("✓ Created Discount A/B test (Free Shipping vs $10 Off)"))

        self.stdout.write(
            self.style.SUCCESS("\n✅ Successfully created all A/B testing example data!")
        )
        self.stdout.write(
            "\nView the results at: http://localhost:8000/admin/ab-testing/"
        )
