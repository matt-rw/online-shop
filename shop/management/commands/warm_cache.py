"""
Management command to warm up the cache with frequently accessed data.

Usage:
    python manage.py warm_cache
"""

from django.core.management.base import BaseCommand

from shop.utils.caching import warm_customer_cache


class Command(BaseCommand):
    help = "Warm up cache with frequently accessed customer-facing data"

    def handle(self, *args, **options):
        self.stdout.write("Starting cache warming...")
        warm_customer_cache()
        self.stdout.write(self.style.SUCCESS("Cache warming completed successfully!"))
