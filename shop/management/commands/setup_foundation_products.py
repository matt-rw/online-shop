"""
Management command to set up Foundation collection products.

Creates:
- Categories: Tops, Bottoms
- Products: Foundation Tee, Foundation Pants
- Sizes: XS, S, M, L, XL
- Colors: Black
- Product variants with all size combinations
"""

from django.core.management.base import BaseCommand

from shop.models import Category, Product, ProductVariant, Size, Color


class Command(BaseCommand):
    help = "Set up Foundation collection categories and products"

    def handle(self, *args, **options):
        self.stdout.write("Setting up Foundation collection...")

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

        # Create Foundation Tee
        tee, created = Product.objects.get_or_create(
            slug="foundation-tee",
            defaults={
                "name": "Foundation Tee",
                "description": "Our signature tee from the Foundation collection. Clean, versatile, and built to last.",
                "category_obj": tops,
                "base_price": 45.00,
                "is_active": True,
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
                    price=45.00,
                    stock_quantity=100,
                    is_active=True,
                    images=["images/white_bg_top.webp"],
                )
                self.stdout.write(f"    Created variant: Foundation Tee - {code}")
        else:
            self.stdout.write("  Foundation Tee already exists")

        # Create Foundation Pants
        pants, created = Product.objects.get_or_create(
            slug="foundation-pants",
            defaults={
                "name": "Foundation Pants",
                "description": "Our signature pants from the Foundation collection. Comfortable, stylish, and designed for everyday wear.",
                "category_obj": bottoms,
                "base_price": 85.00,
                "is_active": True,
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
                    price=85.00,
                    stock_quantity=100,
                    is_active=True,
                    images=["images/white_bg_bottom.webp"],
                )
                self.stdout.write(f"    Created variant: Foundation Pants - {code}")
        else:
            self.stdout.write("  Foundation Pants already exists")

        self.stdout.write(self.style.SUCCESS("\nFoundation collection setup complete!"))
        self.stdout.write(f"  Categories: {Category.objects.count()}")
        self.stdout.write(f"  Products: {Product.objects.count()}")
        self.stdout.write(f"  Variants: {ProductVariant.objects.count()}")
