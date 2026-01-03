"""
Management command to clean up abandoned orders.

Deletes orders with AWAITING_PAYMENT status that are older than a specified age.
These are orders where the customer started checkout but never completed payment.

Usage:
    python manage.py cleanup_abandoned_orders
    python manage.py cleanup_abandoned_orders --hours=24
    python manage.py cleanup_abandoned_orders --dry-run
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from shop.models import Order, OrderItem, OrderStatus


class Command(BaseCommand):
    help = "Clean up abandoned orders (AWAITING_PAYMENT status older than specified hours)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=24,
            help="Delete orders older than this many hours (default: 24)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )

    def handle(self, *args, **options):
        hours = options["hours"]
        dry_run = options["dry_run"]

        cutoff_time = timezone.now() - timedelta(hours=hours)

        # Find abandoned orders
        abandoned_orders = Order.objects.filter(
            status=OrderStatus.AWAITING_PAYMENT,
            created_at__lt=cutoff_time,
        )

        count = abandoned_orders.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("No abandoned orders to clean up."))
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"[DRY RUN] Would delete {count} abandoned order(s):")
            )
            for order in abandoned_orders[:20]:  # Show first 20
                self.stdout.write(f"  - Order #{order.id} (created: {order.created_at})")
            if count > 20:
                self.stdout.write(f"  ... and {count - 20} more")
        else:
            # Delete order items first (due to FK constraints)
            items_deleted = OrderItem.objects.filter(order__in=abandoned_orders).delete()[0]

            # Delete the orders
            orders_deleted = abandoned_orders.delete()[0]

            self.stdout.write(
                self.style.SUCCESS(
                    f"Deleted {orders_deleted} abandoned order(s) and {items_deleted} order item(s)."
                )
            )
