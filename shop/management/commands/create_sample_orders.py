"""
Django management command to create sample orders for customer accounts.
"""
import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from shop.models.cart import Address, Order, OrderItem, OrderStatus
from shop.models.product import ProductVariant


class Command(BaseCommand):
    help = 'Creates sample orders for existing customer accounts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--orders-per-customer',
            type=int,
            default=None,
            help='Average number of orders per customer (default: random 0-3)'
        )

    def handle(self, *args, **options):
        # Get all non-staff customers
        customers = User.objects.filter(is_staff=False, is_superuser=False)
        customer_count = customers.count()

        if customer_count == 0:
            self.stdout.write(self.style.WARNING('No customers found. Run create_sample_customers first.'))
            return

        # Get all product variants
        variants = list(ProductVariant.objects.all())
        if not variants:
            self.stdout.write(self.style.ERROR('No product variants found. Cannot create orders.'))
            return

        self.stdout.write(f'Found {customer_count} customers and {len(variants)} product variants')
        self.stdout.write('Creating sample orders...\n')

        orders_per_customer = options.get('orders_per_customer')
        total_orders = 0

        for customer in customers:
            # Determine number of orders for this customer
            if orders_per_customer:
                num_orders = orders_per_customer
            else:
                # 30% have no orders, 40% have 1 order, 20% have 2, 10% have 3+
                rand = random.random()
                if rand < 0.30:
                    num_orders = 0
                elif rand < 0.70:
                    num_orders = 1
                elif rand < 0.90:
                    num_orders = 2
                else:
                    num_orders = random.randint(2, 5)

            if num_orders == 0:
                continue

            # Create shipping address for this customer
            address = Address.objects.create(
                full_name=f"{customer.first_name} {customer.last_name}",
                line1=f"{random.randint(100, 9999)} {random.choice(['Main', 'Oak', 'Maple', 'Elm', 'Park'])} St",
                city=random.choice(['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix']),
                region=random.choice(['NY', 'CA', 'IL', 'TX', 'AZ']),
                postal_code=f"{random.randint(10000, 99999)}",
                country='US',
                email=customer.email
            )

            # Create orders for this customer
            for i in range(num_orders):
                # Random date between customer join date and now
                days_since_join = (timezone.now().date() - customer.date_joined.date()).days
                if days_since_join > 0:
                    days_ago = random.randint(0, days_since_join)
                    order_date = timezone.now() - timedelta(days=days_ago)
                else:
                    order_date = timezone.now()

                # Order status (90% paid/fulfilled, 10% other)
                if random.random() < 0.90:
                    status = random.choice([OrderStatus.PAID, OrderStatus.FULFILLED, OrderStatus.SHIPPED])
                else:
                    status = random.choice([OrderStatus.CREATED, OrderStatus.AWAITING_PAYMENT, OrderStatus.FAILED])

                # Create order
                order = Order.objects.create(
                    user=customer,
                    email=customer.email,
                    status=status,
                    shipping_address=address,
                    billing_address=address,
                    created_at=order_date
                )

                # Add 1-4 items to the order
                num_items = random.randint(1, 4)
                subtotal = Decimal('0.00')

                for _ in range(num_items):
                    variant = random.choice(variants)
                    quantity = random.randint(1, 3)
                    line_total = variant.price * quantity

                    OrderItem.objects.create(
                        order=order,
                        variant=variant,
                        sku=variant.sku,
                        quantity=quantity,
                        line_total=line_total
                    )

                    subtotal += line_total

                # Calculate totals
                shipping = Decimal('5.99') if subtotal < 50 else Decimal('0.00')
                tax = subtotal * Decimal('0.08')  # 8% tax
                total = subtotal + shipping + tax

                # Update order totals
                order.subtotal = subtotal
                order.shipping = shipping
                order.tax = tax
                order.total = total
                order.save()

                total_orders += 1

            customer_orders = num_orders
            self.stdout.write(
                self.style.SUCCESS(
                    f'  {customer.first_name} {customer.last_name}: {customer_orders} order(s)'
                )
            )

        self.stdout.write(
            self.style.SUCCESS(f'\nSuccessfully created {total_orders} sample orders!')
        )
        self.stdout.write(
            self.style.SUCCESS('The customer analytics dashboard should now display data.')
        )
