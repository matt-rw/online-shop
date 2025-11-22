"""
Django management command to create sample customer accounts for testing.
"""
import random
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Creates sample customer accounts with orders and carts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=20,
            help='Number of sample customers to create (default: 20)'
        )

    def handle(self, *args, **options):
        count = options['count']

        # Sample first names
        first_names = [
            'Emma', 'Liam', 'Olivia', 'Noah', 'Ava', 'Ethan', 'Sophia', 'Mason',
            'Isabella', 'William', 'Mia', 'James', 'Charlotte', 'Benjamin', 'Amelia',
            'Lucas', 'Harper', 'Henry', 'Evelyn', 'Alexander'
        ]

        # Sample last names
        last_names = [
            'Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis',
            'Rodriguez', 'Martinez', 'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson',
            'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin'
        ]

        created_count = 0

        for i in range(count):
            # Generate random customer data
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            username = f"{first_name.lower()}.{last_name.lower()}{random.randint(1, 999)}"
            email = f"{username}@example.com"

            # Skip if username already exists
            if User.objects.filter(username=username).exists():
                continue

            # Random join date (within last 180 days)
            days_ago = random.randint(1, 180)
            join_date = timezone.now() - timedelta(days=days_ago)

            # Create user (customer, not staff)
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_staff=False,
                is_superuser=False,
                is_active=True,
                date_joined=join_date
            )

            # Randomly set last login (70% chance)
            if random.random() < 0.7:
                login_days_ago = random.randint(0, days_ago)
                user.last_login = timezone.now() - timedelta(days=login_days_ago)
                user.save()

            created_count += 1
            self.stdout.write(
                self.style.SUCCESS(f'Created customer: {first_name} {last_name} ({email})')
            )

        self.stdout.write(
            self.style.SUCCESS(f'\nSuccessfully created {created_count} sample customers!')
        )
        self.stdout.write(
            self.style.WARNING('Note: These are test accounts. To create orders, use the create_sample_orders command.')
        )
