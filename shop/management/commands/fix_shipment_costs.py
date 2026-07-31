"""
Fix shipment item costs by distributing the total bulk cost
proportionally by selling price.

Usage:
    python manage.py fix_shipment_costs --dry-run           # Preview
    python manage.py fix_shipment_costs                     # Apply
    python manage.py fix_shipment_costs --shipment-id 1     # Fix specific shipment
"""

from decimal import Decimal, ROUND_HALF_UP

from django.core.management.base import BaseCommand

from shop.models.cart import OrderItem
from shop.models.shipment import Shipment, ShipmentItem


class Command(BaseCommand):
    help = "Redistribute shipment item costs proportionally by selling price"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--shipment-id", type=int, help="Fix a specific shipment")
        parser.add_argument("--total", type=float, help="Override the total items cost to distribute (manufacturing only, not shipping/customs)")
        parser.add_argument("--tee-cost", type=float, help="If you know the per-unit tee cost, set it directly")
        parser.add_argument("--pants-cost", type=float, help="If you know the per-unit pants cost, set it directly")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if options["shipment_id"]:
            shipments = Shipment.objects.filter(id=options["shipment_id"])
        else:
            shipments = Shipment.objects.all()

        for shipment in shipments:
            items = ShipmentItem.objects.filter(shipment=shipment).select_related(
                "variant__product"
            )

            if not items.exists():
                continue

            # Use provided total or calculate from current items_subtotal
            if options.get("total"):
                bulk_total = Decimal(str(options["total"]))
            else:
                bulk_total = shipment.items_subtotal

            if bulk_total <= 0:
                continue

            self.stdout.write(f"\n{'='*70}")
            self.stdout.write(f"Shipment: {shipment.tracking_number or shipment.id}")
            self.stdout.write(f"Total to distribute: ${bulk_total:.2f}")
            self.stdout.write(f"Shipping: ${shipment.shipping_cost:.2f}, Customs: ${shipment.customs_duty:.2f}, Fees: ${shipment.other_fees:.2f}")

            # Calculate total retail value (price × quantity for each item)
            total_retail = Decimal("0")
            for item in items:
                total_retail += item.variant.price * item.quantity

            if total_retail <= 0:
                self.stdout.write(self.style.ERROR("  Total retail value is 0 — can't distribute"))
                continue

            # Check for direct per-product cost overrides
            direct_costs = {}
            if options.get("tee_cost"):
                direct_costs["tee"] = Decimal(str(options["tee_cost"]))
            if options.get("pants_cost"):
                direct_costs["pants"] = Decimal(str(options["pants_cost"]))

            self.stdout.write(f"Total retail value: ${total_retail:.2f}")
            if direct_costs:
                self.stdout.write(f"Direct costs: {direct_costs}")
            self.stdout.write(f"\n{'SKU':<30} {'Product':<25} {'Qty':<6} {'Price':<8} {'Old Cost':<10} {'New Cost':<10} {'Landed':<10} {'Margin':<8}")
            self.stdout.write("-" * 110)

            total_items_count = sum(item.quantity for item in items)
            overhead = shipment.shipping_cost + shipment.customs_duty + shipment.other_fees
            overhead_per_unit = overhead / max(total_items_count, 1)

            for item in items:
                # Check for direct cost override by product name
                product_name = item.variant.product.name.lower()
                if "tee" in product_name and "tee" in direct_costs:
                    new_unit_cost = direct_costs["tee"]
                elif "pant" in product_name and "pants" in direct_costs:
                    new_unit_cost = direct_costs["pants"]
                else:
                    # Price ratio: this item's share of total retail value
                    item_retail = item.variant.price * item.quantity
                    share = item_retail / total_retail
                    item_cost_share = bulk_total * share
                    new_unit_cost = (item_cost_share / item.quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                landed = float(new_unit_cost) + float(overhead_per_unit)
                margin = ((float(item.variant.price) - landed) / float(item.variant.price)) * 100

                old_cost = item.unit_cost

                self.stdout.write(
                    f"{(item.variant.sku or str(item.variant.id)):<30} "
                    f"{item.variant.product.name:<25} "
                    f"{item.quantity:<6} "
                    f"${item.variant.price:<7} "
                    f"${old_cost:<9} "
                    f"${new_unit_cost:<9} "
                    f"${landed:<9.2f} "
                    f"{margin:<7.1f}%"
                )

                if not dry_run:
                    item.unit_cost = new_unit_cost
                    item.save(update_fields=["unit_cost"])

                    # Also update any OrderItems that were allocated from this shipment
                    updated = OrderItem.objects.filter(
                        shipment_item=item
                    ).update(unit_cost=new_unit_cost)
                    if updated:
                        self.stdout.write(f"  → Updated {updated} order item(s)")

                    # Update the product's base_cost to the latest unit cost
                    product = item.variant.product
                    product.base_cost = new_unit_cost
                    product.save(update_fields=["base_cost"])

            self.stdout.write(f"\nOverhead per unit: ${overhead_per_unit:.2f}")

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDry run — no changes made."))
        else:
            self.stdout.write(self.style.SUCCESS("\nCosts updated successfully."))
