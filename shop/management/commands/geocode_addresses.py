"""
Management command to geocode addresses that are missing coordinates.
"""

import time

from django.core.management.base import BaseCommand

from shop.models import Address, SiteSettings
from shop.utils.geocoding import geocode_address


class Command(BaseCommand):
    help = 'Geocode addresses missing latitude/longitude coordinates'

    def add_arguments(self, parser):
        parser.add_argument(
            '--warehouse-only',
            action='store_true',
            help='Only geocode the warehouse address',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Maximum number of addresses to geocode (default: 100)',
        )

    def handle(self, *args, **options):
        warehouse_only = options['warehouse_only']
        limit = options['limit']

        # Geocode warehouse
        self.stdout.write('Geocoding warehouse...')
        site_settings = SiteSettings.load()
        if site_settings.warehouse_city and site_settings.warehouse_state:
            if site_settings.warehouse_latitude and site_settings.warehouse_longitude:
                self.stdout.write(self.style.SUCCESS(
                    f'  Warehouse already has coordinates: ({site_settings.warehouse_latitude}, {site_settings.warehouse_longitude})'
                ))
            else:
                coords = site_settings.geocode_warehouse()
                if coords:
                    self.stdout.write(self.style.SUCCESS(
                        f'  Geocoded warehouse to: ({coords[0]}, {coords[1]})'
                    ))
                else:
                    self.stdout.write(self.style.WARNING('  Could not geocode warehouse'))
        else:
            self.stdout.write(self.style.WARNING('  Warehouse address not configured'))

        if warehouse_only:
            return

        # Geocode shipping addresses
        self.stdout.write(f'\nGeocoding up to {limit} addresses without coordinates...')
        addresses = Address.objects.filter(
            latitude__isnull=True
        ).exclude(
            city=''
        )[:limit]

        total = addresses.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS('All addresses already have coordinates!'))
            return

        self.stdout.write(f'Found {total} addresses to geocode')

        geocoded = 0
        failed = 0

        for i, address in enumerate(addresses):
            self.stdout.write(f'  [{i+1}/{total}] {address.city}, {address.region} {address.postal_code}...', ending='')

            coords = geocode_address(
                address.city,
                address.region,
                address.postal_code,
                address.country or 'US'
            )

            if coords:
                address.latitude, address.longitude = coords
                address.save(update_fields=['latitude', 'longitude'])
                self.stdout.write(self.style.SUCCESS(f' ({coords[0]:.4f}, {coords[1]:.4f})'))
                geocoded += 1
            else:
                self.stdout.write(self.style.WARNING(' FAILED'))
                failed += 1

            # Rate limiting - Nominatim requires 1 second between requests
            if i < total - 1:
                time.sleep(1)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Geocoded: {geocoded}'))
        if failed:
            self.stdout.write(self.style.WARNING(f'Failed: {failed}'))
