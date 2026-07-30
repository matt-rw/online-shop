"""
One-time stock reconciliation command.
Finds all completed orders that never had their stock deducted
and applies the corrections with audit logging.

Usage:
    python manage.py reconcile_stock --dry-run    # Preview changes
    python manage.py reconcile_stock              # Apply corrections
"""

from django.core.management.base import BaseCommand
from django.db.models import Sum

from shop.models.cart import Order, OrderItem
from shop.models.inventory import StockAdjustment
from shop.models.product import ProductVariant


class Command(BaseCommand):
    help = "Reconcile stock by deducting sold quantities that were never deducted from completed orders"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without applying them",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        completed_statuses = ["PAID", "SHIPPED", "HAND_DELIVERED", "FULFILLED"]

        # Calculate total sold per variant from completed orders
        sold_by_variant = dict(
            OrderItem.objects.filter(
                order__status__in=completed_statuses,
                variant__isnull=False,
            ).values("variant_id").annotate(
                total_sold=Sum("quantity")
            ).values_list("variant_id", "total_sold")
        )

        # Calculate total already deducted per variant from audit log (order_sold type)
        already_deducted = {}
        for adj in StockAdjustment.objects.filter(adjustment_type="order_sold").values("variant_id").annotate(
            total=Sum("difference")
        ):
            # difference is negative for deductions
            already_deducted[adj["variant_id"]] = abs(adj["total"])

        self.stdout.write(f"\n{'Product':<35} {'SKU':<15} {'Sold':<8} {'Deducted':<10} {'Missing':<10} {'Current':<10} {'Corrected':<10}")
        self.stdout.write("-" * 100)

        corrections = 0
        for variant_id, total_sold in sold_by_variant.items():
            try:
                variant = ProductVariant.objects.select_related("product").get(id=variant_id)
            except ProductVariant.DoesNotExist:
                continue

            deducted = already_deducted.get(variant_id, 0)
            missing = total_sold - deducted

            if missing <= 0:
                continue

            new_stock = max(0, variant.stock_quantity - missing)

            name = f"{variant.product.name}"
            sku = variant.sku or str(variant.id)

            self.stdout.write(
                f"{name:<35} {sku:<15} {total_sold:<8} {deducted:<10} {missing:<10} {variant.stock_quantity:<10} {new_stock:<10}"
            )

            if not dry_run:
                from shop.utils.stock import deduct_stock
                deduct_stock(
                    variant, missing, "count_correction",
                    f"Reconciliation: {missing} units sold but never deducted from stock"
                )
                corrections += 1

        if dry_run:
            self.stdout.write(self.style.WARNING(f"\nDry run — no changes made. Run without --dry-run to apply."))
        else:
            self.stdout.write(self.style.SUCCESS(f"\nApplied {corrections} stock corrections."))
