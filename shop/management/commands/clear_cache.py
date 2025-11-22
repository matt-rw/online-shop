"""
Management command to clear cache.

Usage:
    python manage.py clear_cache [--products-only]
"""

from django.core.management.base import BaseCommand

from shop.utils.caching import clear_all_cache, clear_product_cache


class Command(BaseCommand):
    help = "Clear cache data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--products-only",
            action="store_true",
            help="Clear only product cache, not everything",
        )

    def handle(self, *args, **options):
        if options["products_only"]:
            self.stdout.write("Clearing product cache...")
            clear_product_cache()
            self.stdout.write(self.style.SUCCESS("Product cache cleared!"))
        else:
            self.stdout.write(self.style.WARNING("Clearing ALL cache..."))
            clear_all_cache()
            self.stdout.write(self.style.SUCCESS("All cache cleared!"))
