"""
Find and clean up duplicate/orphaned variants.
Shows all variants per product so you can see what's real vs duplicate.

Usage:
    python manage.py cleanup_variants --dry-run    # Preview what would be removed
    python manage.py cleanup_variants              # Remove duplicates
"""

from django.core.management.base import BaseCommand
from django.db.models import Count

from shop.models.product import Product, ProductVariant


class Command(BaseCommand):
    help = "Find and remove duplicate/orphaned product variants"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview duplicates without removing them",
        )
        parser.add_argument(
            "--show-all",
            action="store_true",
            help="Show all variants including legitimate ones",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        show_all = options["show_all"]

        for product in Product.objects.filter(is_active=True).order_by("name"):
            variants = ProductVariant.objects.filter(product=product).order_by("sku")
            total = variants.count()

            self.stdout.write(f"\n{product.name} — {total} variants")
            self.stdout.write(f"{'ID':<6} {'SKU':<35} {'Size':<6} {'Color':<10} {'Stock':<8} {'Active':<8} {'Has Attrs':<10} {'Orders':<8}")
            self.stdout.write("-" * 95)

            # Track seen size/color combos to find duplicates
            seen = {}
            duplicates = []

            for v in variants:
                # Get unified attributes
                attrs = list(v.attributes.select_related("attribute").all())
                has_attrs = len(attrs) > 0

                # Get size/color from legacy or unified
                size = ""
                color = ""
                if v.size:
                    size = v.size.code
                if v.color:
                    color = v.color.name

                for attr in attrs:
                    if attr.attribute.slug == "size" or attr.attribute.name.lower() == "size":
                        size = attr.value
                    if attr.attribute.slug == "color" or attr.attribute.name.lower() == "color":
                        color = attr.value

                # Check for orders using this variant
                from shop.models.cart import OrderItem
                order_count = OrderItem.objects.filter(variant=v).count()

                key = f"{size}-{color}".lower()
                is_dup = False
                if key in seen:
                    is_dup = True
                    duplicates.append(v)
                else:
                    seen[key] = v.id

                marker = " ** DUPLICATE" if is_dup else ""
                if show_all or is_dup or not v.is_active:
                    self.stdout.write(
                        f"{v.id:<6} {(v.sku or 'no-sku'):<35} {size:<6} {color:<10} {v.stock_quantity:<8} "
                        f"{'Yes' if v.is_active else 'No':<8} {'Yes' if has_attrs else 'No':<10} {order_count:<8}"
                        + self.style.WARNING(marker)
                    )

            if not duplicates and not show_all:
                self.stdout.write(f"  No duplicates found ({total} variants, all unique)")
            elif duplicates:
                self.stdout.write(self.style.WARNING(f"\n  {len(duplicates)} duplicates found"))
                if not dry_run:
                    for v in duplicates:
                        order_count = OrderItem.objects.filter(variant=v).count()
                        if order_count > 0:
                            self.stdout.write(self.style.ERROR(
                                f"  SKIPPING variant {v.id} ({v.sku}) — has {order_count} orders linked"
                            ))
                        else:
                            self.stdout.write(f"  Deleting variant {v.id} ({v.sku})")
                            v.delete()

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDry run — no changes made."))
