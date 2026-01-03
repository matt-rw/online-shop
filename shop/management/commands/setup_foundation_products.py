"""
Management command to set up Foundation collection products.

Creates:
- Categories: Tops, Bottoms
- Products: Foundation Tee, Foundation Pants
- Sizes: XS, S, M, L, XL
- Colors: Black
- Product variants with all size combinations and actual product photos

Usage:
    python manage.py setup_foundation_products
    python manage.py setup_foundation_products --reset  # Delete and recreate
"""

from django.core.management.base import BaseCommand

from shop.models import Category, Product, ProductVariant, Size, Color


class Command(BaseCommand):
    help = "Set up Foundation collection categories and products with photos"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing Foundation products and recreate them",
        )

    def handle(self, *args, **options):
        self.stdout.write("Setting up Foundation collection...")

        # Handle reset option
        if options["reset"]:
            self.stdout.write(self.style.WARNING("Resetting Foundation products..."))
            # Delete variants first (due to FK constraint)
            deleted_variants = ProductVariant.objects.filter(
                product__slug__in=["foundation-tee", "foundation-pants"]
            ).delete()
            self.stdout.write(f"  Deleted {deleted_variants[0]} variants")

            # Delete products
            deleted_products = Product.objects.filter(
                slug__in=["foundation-tee", "foundation-pants"]
            ).delete()
            self.stdout.write(f"  Deleted {deleted_products[0]} products")

        # Create sizes
        sizes_data = [
            ("XS", "XS"),
            ("S", "S"),
            ("M", "M"),
            ("L", "L"),
            ("XL", "XL"),
        ]
        sizes = {}
        for code, label in sizes_data:
            size, created = Size.objects.get_or_create(code=code, defaults={"label": label})
            sizes[code] = size
            if created:
                self.stdout.write(f"  Created size: {code}")

        # Create colors
        black, created = Color.objects.get_or_create(name="Black")
        if created:
            self.stdout.write("  Created color: Black")

        # Create categories
        tops, created = Category.objects.get_or_create(
            slug="tops",
            defaults={
                "name": "Tops",
                "description": "T-shirts, shirts, and other tops",
                "uses_size": True,
                "uses_color": True,
            },
        )
        if created:
            self.stdout.write("  Created category: Tops")

        bottoms, created = Category.objects.get_or_create(
            slug="bottoms",
            defaults={
                "name": "Bottoms",
                "description": "Pants, shorts, and other bottoms",
                "uses_size": True,
                "uses_color": True,
            },
        )
        if created:
            self.stdout.write("  Created category: Bottoms")

        # Product images - optimized photos from product-pics folder
        tee_images = [
            "images/product-pics/front-top.jpg",
            "images/product-pics/side-top.jpg",
            "images/product-pics/top-detail.jpg",
        ]

        pants_images = [
            "images/product-pics/front-bottoms.jpg",
            "images/product-pics/side-bottoms.jpg",
            "images/product-pics/back-bottoms.jpg",
        ]

        # Create Foundation Tee
        tee, created = Product.objects.get_or_create(
            slug="foundation-tee",
            defaults={
                "name": "Foundation Tee",
                "description": "Our signature tee from the Foundation collection. Premium heavyweight cotton with a relaxed fit. Clean, versatile, and built to last.",
                "category_obj": tops,
                "base_price": 50.00,
                "is_active": True,
                "available_for_purchase": False,  # Coming soon
                "featured": True,
            },
        )
        if created:
            self.stdout.write("  Created product: Foundation Tee")
            # Create variants for all sizes
            for code, size in sizes.items():
                ProductVariant.objects.create(
                    product=tee,
                    size=size,
                    color=black,
                    price=50.00,
                    stock_quantity=100,
                    is_active=True,
                    images=tee_images,
                )
                self.stdout.write(f"    Created variant: Foundation Tee - {code}")
        else:
            self.stdout.write("  Foundation Tee already exists")
            # Update images on existing variants if needed
            updated = tee.variants.update(images=tee_images)
            if updated:
                self.stdout.write(f"    Updated {updated} variant images")

        # Create Foundation Pants
        pants, created = Product.objects.get_or_create(
            slug="foundation-pants",
            defaults={
                "name": "Foundation Pants",
                "description": "Our signature pants from the Foundation collection. Comfortable, stylish, and designed for everyday wear. Relaxed fit with a tapered leg.",
                "category_obj": bottoms,
                "base_price": 65.00,
                "is_active": True,
                "available_for_purchase": False,  # Coming soon
                "featured": True,
            },
        )
        if created:
            self.stdout.write("  Created product: Foundation Pants")
            # Create variants for all sizes
            for code, size in sizes.items():
                ProductVariant.objects.create(
                    product=pants,
                    size=size,
                    color=black,
                    price=65.00,
                    stock_quantity=100,
                    is_active=True,
                    images=pants_images,
                )
                self.stdout.write(f"    Created variant: Foundation Pants - {code}")
        else:
            self.stdout.write("  Foundation Pants already exists")
            # Update images on existing variants if needed
            updated = pants.variants.update(images=pants_images)
            if updated:
                self.stdout.write(f"    Updated {updated} variant images")

        self.stdout.write(self.style.SUCCESS("\nFoundation collection setup complete!"))
        self.stdout.write(f"  Categories: {Category.objects.count()}")
        self.stdout.write(f"  Products: {Product.objects.count()}")
        self.stdout.write(f"  Variants: {ProductVariant.objects.count()}")
        self.stdout.write("\nProduct images:")
        self.stdout.write(f"  Foundation Tee: {', '.join(tee_images)}")
        self.stdout.write(f"  Foundation Pants: {', '.join(pants_images)}")
        self.stdout.write("\nNote: Products are set to 'Not Available for Purchase' by default.")
        self.stdout.write("Update via admin dashboard when ready to launch.")
