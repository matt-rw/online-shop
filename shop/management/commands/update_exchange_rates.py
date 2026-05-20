"""
Management command to update currency exchange rates from free APIs.

Run daily via cron:
    0 6 * * * python manage.py update_exchange_rates

Or manually:
    python manage.py update_exchange_rates
    python manage.py update_exchange_rates --force  # Update even if recently updated
    python manage.py update_exchange_rates --source frankfurter  # Use specific source
"""
import logging
from datetime import timedelta
from decimal import Decimal

import requests

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Update currency exchange rates from free open-source APIs'

    # Free API sources (no API key required)
    API_SOURCES = {
        # Frankfurter - Open source, uses European Central Bank data
        # https://www.frankfurter.app/docs/
        'frankfurter': "https://api.frankfurter.app/latest?from=USD",

        # ExchangeRate API - Free tier
        # https://www.exchangerate-api.com/docs/free
        'exchangerate': "https://api.exchangerate-api.com/v4/latest/USD",
    }

    DEFAULT_SOURCE = 'exchangerate'  # Use this as default since it includes RUB

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update even if rates were updated recently',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--source',
            type=str,
            choices=['frankfurter', 'exchangerate'],
            default=self.DEFAULT_SOURCE,
            help=f'API source to use (default: {self.DEFAULT_SOURCE})',
        )

    def handle(self, *args, **options):
        from shop.models import Currency

        force = options['force']
        dry_run = options['dry_run']
        source = options['source']

        # Get all active currencies (except USD which is always 1.0)
        currencies = Currency.objects.filter(is_active=True).exclude(code='USD')

        if not currencies.exists():
            self.stdout.write(self.style.WARNING('No active currencies found (besides USD).'))
            return

        # Check if we should skip update (updated within last 12 hours)
        if not force:
            recent_update = Currency.objects.filter(
                rate_updated_at__gte=timezone.now() - timedelta(hours=12)
            ).exclude(code='USD').first()

            if recent_update:
                self.stdout.write(self.style.WARNING(
                    f'Rates were updated {recent_update.rate_updated_at}. Use --force to update anyway.'
                ))
                return

        # Fetch rates from API
        api_url = self.API_SOURCES[source]
        try:
            self.stdout.write(f'Fetching exchange rates from {source} ({api_url})...')
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f'Failed to fetch exchange rates: {e}'))
            logger.error(f'Exchange rate API error ({source}): {e}')
            # Try fallback source
            fallback = 'frankfurter' if source == 'exchangerate' else 'exchangerate'
            if source != fallback:
                self.stdout.write(f'Trying fallback source ({fallback})...')
                return self.handle(*args, **{**options, 'source': fallback})
            return

        rates = data.get('rates', {})
        if not rates:
            self.stdout.write(self.style.ERROR('No rates found in API response'))
            return

        self.stdout.write(f'Received rates for {len(rates)} currencies (source: {source})')

        # Update each currency
        updated_count = 0
        now = timezone.now()

        for currency in currencies:
            if currency.code in rates:
                new_rate = Decimal(str(rates[currency.code]))
                old_rate = currency.exchange_rate

                if dry_run:
                    self.stdout.write(
                        f'  {currency.code}: {old_rate} -> {new_rate} (dry run)'
                    )
                else:
                    currency.exchange_rate = new_rate
                    currency.rate_updated_at = now
                    currency.save(update_fields=['exchange_rate', 'rate_updated_at'])
                    self.stdout.write(
                        f'  {currency.code}: {old_rate} -> {new_rate}'
                    )
                updated_count += 1
            else:
                self.stdout.write(self.style.WARNING(
                    f'  {currency.code}: No rate found in API response'
                ))

        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f'\nDry run complete. Would update {updated_count} currencies.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\nSuccessfully updated {updated_count} exchange rates.'
            ))
            logger.info(f'Updated {updated_count} exchange rates')
