from django.core.management.base import BaseCommand
from shop.models import Product, Size, Color, ProductVariant
from decimal import Decimal
import random


class Command(BaseCommand):
    help = 'Populate database with realistic clothing products for Blueprint Apparel'

    def handle(self, *args, **options):
        self.stdout.write('Creating sizes...')
        sizes_data = [
            ('XS', 'Extra Small'),
            ('S', 'Small'),
            ('M', 'Medium'),
            ('L', 'Large'),
            ('XL', 'Extra Large'),
            ('XXL', '2X Large'),
        ]

        sizes = {}
        for code, label in sizes_data:
            size, created = Size.objects.get_or_create(
                code=code,
                defaults={'label': label}
            )
            sizes[code] = size
            if created:
                self.stdout.write(f'  Created size: {label}')

        self.stdout.write('\nCreating colors...')
        colors_data = [
            'Black', 'White', 'Navy', 'Gray', 'Charcoal',
            'Olive', 'Burgundy', 'Forest Green', 'Royal Blue',
            'Cream', 'Tan', 'Rust', 'Sage', 'Dusty Rose'
        ]

        colors = {}
        for color_name in colors_data:
            color, created = Color.objects.get_or_create(name=color_name)
            colors[color_name] = color
            if created:
                self.stdout.write(f'  Created color: {color_name}')

        self.stdout.write('\nCreating products...')
        products_data = [
            # T-Shirts & Tops
            {
                'name': 'Essential Crew Neck Tee',
                'slug': 'essential-crew-neck-tee',
                'base_price': Decimal('28.00'),
                'colors': ['Black', 'White', 'Navy', 'Gray', 'Olive'],
                'sizes': ['XS', 'S', 'M', 'L', 'XL', 'XXL'],
            },
            {
                'name': 'Premium V-Neck Tee',
                'slug': 'premium-v-neck-tee',
                'base_price': Decimal('32.00'),
                'colors': ['Black', 'White', 'Charcoal', 'Navy'],
                'sizes': ['S', 'M', 'L', 'XL'],
            },
            {
                'name': 'Classic Henley',
                'slug': 'classic-henley',
                'base_price': Decimal('45.00'),
                'colors': ['Gray', 'Navy', 'Burgundy', 'Olive'],
                'sizes': ['S', 'M', 'L', 'XL', 'XXL'],
            },
            {
                'name': 'Long Sleeve Crew',
                'slug': 'long-sleeve-crew',
                'base_price': Decimal('38.00'),
                'colors': ['Black', 'White', 'Navy', 'Forest Green'],
                'sizes': ['XS', 'S', 'M', 'L', 'XL'],
            },

            # Hoodies & Sweatshirts
            {
                'name': 'Classic Pullover Hoodie',
                'slug': 'classic-pullover-hoodie',
                'base_price': Decimal('68.00'),
                'colors': ['Black', 'Gray', 'Navy', 'Burgundy', 'Forest Green'],
                'sizes': ['S', 'M', 'L', 'XL', 'XXL'],
            },
            {
                'name': 'Zip-Up Hoodie',
                'slug': 'zip-up-hoodie',
                'base_price': Decimal('72.00'),
                'colors': ['Charcoal', 'Navy', 'Black'],
                'sizes': ['M', 'L', 'XL', 'XXL'],
            },
            {
                'name': 'Premium Crewneck Sweatshirt',
                'slug': 'premium-crewneck-sweatshirt',
                'base_price': Decimal('58.00'),
                'colors': ['Gray', 'Cream', 'Sage', 'Rust'],
                'sizes': ['S', 'M', 'L', 'XL'],
            },

            # Pants & Bottoms
            {
                'name': 'Slim Fit Chinos',
                'slug': 'slim-fit-chinos',
                'base_price': Decimal('78.00'),
                'colors': ['Navy', 'Tan', 'Olive', 'Charcoal'],
                'sizes': ['S', 'M', 'L', 'XL'],
            },
            {
                'name': 'Relaxed Joggers',
                'slug': 'relaxed-joggers',
                'base_price': Decimal('62.00'),
                'colors': ['Black', 'Gray', 'Navy'],
                'sizes': ['S', 'M', 'L', 'XL', 'XXL'],
            },
            {
                'name': 'Classic Denim Jeans',
                'slug': 'classic-denim-jeans',
                'base_price': Decimal('88.00'),
                'colors': ['Navy', 'Black'],
                'sizes': ['S', 'M', 'L', 'XL'],
            },

            # Outerwear
            {
                'name': 'Canvas Work Jacket',
                'slug': 'canvas-work-jacket',
                'base_price': Decimal('118.00'),
                'colors': ['Tan', 'Olive', 'Navy'],
                'sizes': ['M', 'L', 'XL', 'XXL'],
            },
            {
                'name': 'Quilted Bomber',
                'slug': 'quilted-bomber',
                'base_price': Decimal('145.00'),
                'colors': ['Black', 'Navy', 'Olive'],
                'sizes': ['S', 'M', 'L', 'XL'],
            },

            # Accessories
            {
                'name': 'Blueprint Baseball Cap',
                'slug': 'blueprint-baseball-cap',
                'base_price': Decimal('28.00'),
                'colors': ['Black', 'Navy', 'Charcoal'],
                'sizes': ['M', 'L'],  # One size fits most, but keeping structure
            },
            {
                'name': 'Essential Beanie',
                'slug': 'essential-beanie',
                'base_price': Decimal('22.00'),
                'colors': ['Black', 'Gray', 'Navy', 'Burgundy'],
                'sizes': ['M'],  # One size
            },
        ]

        products_created = 0
        variants_created = 0

        for product_data in products_data:
            product, created = Product.objects.get_or_create(
                slug=product_data['slug'],
                defaults={
                    'name': product_data['name'],
                    'base_price': product_data['base_price'],
                    'is_active': True
                }
            )

            if created:
                products_created += 1
                self.stdout.write(f'  Created product: {product.name}')

                # Create variants for each color/size combination
                for color_name in product_data['colors']:
                    for size_code in product_data['sizes']:
                        # Randomize stock levels for realism
                        stock_options = [0, 0, 5, 8, 12, 15, 20, 25, 30, 45, 50, 75, 100]
                        stock = random.choice(stock_options)

                        # Some variants might be inactive (discontinued colors/sizes)
                        is_active = random.choice([True, True, True, True, False])

                        # Variant price usually matches base price, but could vary
                        variant_price = product_data['base_price']

                        variant, v_created = ProductVariant.objects.get_or_create(
                            product=product,
                            color=colors[color_name],
                            size=sizes[size_code],
                            defaults={
                                'stock_quantity': stock,
                                'price': variant_price,
                                'is_active': is_active
                            }
                        )

                        if v_created:
                            variants_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'\nSuccessfully created {products_created} products and {variants_created} variants!'
            )
        )

        # Print summary
        self.stdout.write('\nSummary:')
        self.stdout.write(f'  Total Products: {Product.objects.count()}')
        self.stdout.write(f'  Active Products: {Product.objects.filter(is_active=True).count()}')
        self.stdout.write(f'  Total Variants: {ProductVariant.objects.count()}')
        self.stdout.write(f'  Total Stock Units: {sum(v.stock_quantity for v in ProductVariant.objects.all())}')
        self.stdout.write(f'  Low Stock Variants (<10): {ProductVariant.objects.filter(stock_quantity__lt=10, stock_quantity__gt=0).count()}')
        self.stdout.write(f'  Out of Stock Variants: {ProductVariant.objects.filter(stock_quantity=0).count()}')
