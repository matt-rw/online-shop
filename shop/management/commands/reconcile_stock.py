"""
Stock reconciliation command.
Calculates correct stock as: total received from shipments - total sold from orders.
Compares against current stock_quantity and shows/applies corrections.

Usage:
    python manage.py reconcile_stock --dry-run    # Preview changes
    python manage.py reconcile_stock              # Apply corrections
"""

from django.core.management.base import BaseCommand
from django.db.models import Sum

from shop.models.cart import OrderItem
from shop.models.product import ProductVariant
from shop.models.shipment import ShipmentItem


class Command(BaseCommand):
    help = "Reconcile stock: correct stock = received from shipments - sold from orders"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without applying them",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        completed_statuses = ["PAID", "SHIPPED", "HAND_DELIVERED", "FULFILLED"]

        variants = ProductVariant.objects.filter(
            product__is_active=True
        ).exclude(product__slug__startswith="test-").select_related("product")

        self.stdout.write(f"\n{'Product':<35} {'SKU':<25} {'Received':<10} {'Sold':<8} {'Correct':<10} {'Current':<10} {'Diff':<8}")
        self.stdout.write("-" * 110)

        corrections = 0
        total_diff = 0

        for variant in variants:
            # Total received from delivered shipments
            received = ShipmentItem.objects.filter(
                variant=variant, shipment__status="delivered"
            ).aggregate(total=Sum("received_quantity"))["total"] or 0

            # Total sold from completed orders
            sold = OrderItem.objects.filter(
                variant=variant,
                order__status__in=completed_statuses,
            ).aggregate(total=Sum("quantity"))["total"] or 0

            correct_stock = max(0, received - sold)
            current = variant.stock_quantity
            diff = current - correct_stock

            if diff == 0:
                continue

            name = variant.product.name
            sku = variant.sku or str(variant.id)

            color = self.style.ERROR if diff > 0 else self.style.SUCCESS
            self.stdout.write(
                f"{name:<35} {sku:<25} {received:<10} {sold:<8} {correct_stock:<10} {current:<10} "
                + color(f"{diff:+d}")
            )

            total_diff += abs(diff)
            corrections += 1

            if not dry_run:
                from shop.utils.stock import adjust_stock
                adjust_stock(
                    variant, correct_stock, "count_correction",
                    f"Reconciliation: received={received}, sold={sold}, was={current}"
                )

        self.stdout.write(f"\n{corrections} variants with discrepancies. Total unit difference: {total_diff}")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no changes made. Run without --dry-run to apply."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Applied {corrections} stock corrections."))
