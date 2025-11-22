import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from faker import Faker

from shop.models import EmailSubscription, SMSSubscription


class Command(BaseCommand):
    help = "Populate database with random email and SMS subscribers for testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--email", type=int, default=150, help="Number of email subscribers to create"
        )
        parser.add_argument(
            "--sms", type=int, default=100, help="Number of SMS subscribers to create"
        )

    def handle(self, *args, **options):
        fake = Faker()
        email_count = options["email"]
        sms_count = options["sms"]

        self.stdout.write(
            f"Creating {email_count} email subscribers and {sms_count} SMS subscribers..."
        )

        # Generate email subscribers
        email_created = 0
        for i in range(email_count):
            try:
                # Random date within the past 365 days
                days_ago = random.randint(0, 365)
                hours_ago = random.randint(0, 23)
                minutes_ago = random.randint(0, 59)

                subscribed_at = timezone.now() - timedelta(
                    days=days_ago, hours=hours_ago, minutes=minutes_ago
                )

                # Create subscriber
                email = fake.unique.email()
                subscriber = EmailSubscription(
                    email=email,
                    is_confirmed=random.choice([True, True, True, False]),  # 75% confirmed
                    source=random.choice(["site_form", "popup", "checkout", "csv_upload"]),
                    is_active=random.choice([True, True, True, True, False]),  # 80% active
                )
                subscriber.save()

                # Manually set the subscribed_at time (since auto_now_add is set)
                EmailSubscription.objects.filter(id=subscriber.id).update(
                    subscribed_at=subscribed_at
                )

                email_created += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Failed to create email subscriber: {e}"))

        # Generate SMS subscribers
        sms_created = 0
        for i in range(sms_count):
            try:
                # Random date within the past 365 days
                days_ago = random.randint(0, 365)
                hours_ago = random.randint(0, 23)
                minutes_ago = random.randint(0, 59)

                subscribed_at = timezone.now() - timedelta(
                    days=days_ago, hours=hours_ago, minutes=minutes_ago
                )

                # Create subscriber with US phone number
                phone = f"+1{random.randint(2000000000, 9999999999)}"
                subscriber = SMSSubscription(
                    phone_number=phone,
                    is_confirmed=random.choice([True, True, True, False]),  # 75% confirmed
                    source=random.choice(["site_form", "popup", "checkout", "csv_upload"]),
                    is_active=random.choice([True, True, True, True, False]),  # 80% active
                )
                subscriber.save()

                # Manually set the subscribed_at time
                SMSSubscription.objects.filter(id=subscriber.id).update(subscribed_at=subscribed_at)

                sms_created += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Failed to create SMS subscriber: {e}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created {email_created} email subscribers and {sms_created} SMS subscribers!"
            )
        )
