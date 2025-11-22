from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from shop.models import Discount, Product


class Command(BaseCommand):
    help = "Populate database with example discount codes"

    def handle(self, *args, **kwargs):
        self.stdout.write("Populating discounts...")

        # Clear existing discounts
        Discount.objects.all().delete()

        # Get some products for product-specific discounts
        products = list(Product.objects.all()[:5])

        discounts_data = [
            {
                "name": "Summer Sale 2025",
                "code": "SUMMER25",
                "discount_type": "percentage",
                "value": Decimal("25.00"),
                "min_purchase_amount": Decimal("50.00"),
                "max_uses": 500,
                "valid_from": timezone.now(),
                "valid_until": timezone.now() + timedelta(days=60),
                "is_active": True,
                "applies_to_all": True,
            },
            {
                "name": "New Customer Welcome",
                "code": "WELCOME15",
                "discount_type": "percentage",
                "value": Decimal("15.00"),
                "min_purchase_amount": None,
                "max_uses": None,
                "valid_from": timezone.now(),
                "valid_until": None,
                "is_active": True,
                "applies_to_all": True,
            },
            {
                "name": "Free Shipping",
                "code": "FREESHIP",
                "discount_type": "fixed",
                "value": Decimal("10.00"),
                "min_purchase_amount": Decimal("75.00"),
                "max_uses": None,
                "valid_from": timezone.now(),
                "valid_until": timezone.now() + timedelta(days=90),
                "is_active": True,
                "applies_to_all": True,
            },
            {
                "name": "Weekend Flash Sale",
                "code": "WEEKEND30",
                "discount_type": "percentage",
                "value": Decimal("30.00"),
                "min_purchase_amount": Decimal("100.00"),
                "max_uses": 100,
                "valid_from": timezone.now(),
                "valid_until": timezone.now() + timedelta(days=3),
                "is_active": True,
                "applies_to_all": True,
            },
            {
                "name": "VIP Members Only",
                "code": "VIP20",
                "discount_type": "percentage",
                "value": Decimal("20.00"),
                "min_purchase_amount": None,
                "max_uses": None,
                "valid_from": timezone.now(),
                "valid_until": timezone.now() + timedelta(days=365),
                "is_active": True,
                "applies_to_all": True,
            },
            {
                "name": "T-Shirt Special",
                "code": "TSHIRT10",
                "discount_type": "fixed",
                "value": Decimal("10.00"),
                "min_purchase_amount": None,
                "max_uses": 200,
                "valid_from": timezone.now(),
                "valid_until": timezone.now() + timedelta(days=30),
                "is_active": True,
                "applies_to_all": False,
                "products": products[:2] if len(products) >= 2 else [],
            },
            {
                "name": "Buy One Get One",
                "code": "BOGO",
                "discount_type": "bogo",
                "value": Decimal("50.00"),
                "min_purchase_amount": None,
                "max_uses": None,
                "valid_from": timezone.now(),
                "valid_until": timezone.now() + timedelta(days=45),
                "is_active": True,
                "applies_to_all": False,
                "products": products[2:4] if len(products) >= 4 else [],
            },
            {
                "name": "Holiday Mega Sale",
                "code": "HOLIDAY40",
                "discount_type": "percentage",
                "value": Decimal("40.00"),
                "min_purchase_amount": Decimal("150.00"),
                "max_uses": 50,
                "valid_from": timezone.now() + timedelta(days=30),
                "valid_until": timezone.now() + timedelta(days=45),
                "is_active": True,
                "applies_to_all": True,
            },
            {
                "name": "$5 Off Clearance",
                "code": "CLEAR5",
                "discount_type": "fixed",
                "value": Decimal("5.00"),
                "min_purchase_amount": Decimal("25.00"),
                "max_uses": None,
                "valid_from": timezone.now(),
                "valid_until": None,
                "is_active": True,
                "applies_to_all": True,
            },
            {
                "name": "Student Discount",
                "code": "STUDENT10",
                "discount_type": "percentage",
                "value": Decimal("10.00"),
                "min_purchase_amount": None,
                "max_uses": None,
                "valid_from": timezone.now(),
                "valid_until": None,
                "is_active": True,
                "applies_to_all": True,
            },
        ]

        for discount_data in discounts_data:
            products_to_link = discount_data.pop("products", [])
            discount = Discount.objects.create(**discount_data)
            if products_to_link:
                discount.products.set(products_to_link)

            self.stdout.write(
                self.style.SUCCESS(f"Created discount: {discount.name} ({discount.code})")
            )

        self.stdout.write(
            self.style.SUCCESS(f"\nSuccessfully created {len(discounts_data)} discounts!")
        )
