from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from shop.models import Product, ProductVariant, Shipment, ShipmentItem

# Get some existing products and variants
products = Product.objects.all()[:3]  # Get first 3 products
if not products:
    print("No products found. Please create some products first.")
    exit()

# Create sample shipments
shipments_data = [
    {
        "tracking_number": "SHP-2025-001",
        "supplier": "Premium Textiles Co.",
        "status": "delivered",
        "date_shipped": timezone.now().date() - timedelta(days=10),
        "expected_date": timezone.now().date() - timedelta(days=3),
        "date_received": timezone.now().date() - timedelta(days=2),
        "manufacturing_cost": Decimal("2500.00"),
        "shipping_cost": Decimal("350.00"),
        "customs_duty": Decimal("180.00"),
        "other_fees": Decimal("75.00"),
        "notes": "First shipment of winter collection. All items received in good condition.",
    },
    {
        "tracking_number": "SHP-2025-002",
        "supplier": "Global Fabrics Ltd.",
        "status": "in-transit",
        "date_shipped": timezone.now().date() - timedelta(days=5),
        "expected_date": timezone.now().date() + timedelta(days=2),
        "date_received": None,
        "manufacturing_cost": Decimal("1800.00"),
        "shipping_cost": Decimal("280.00"),
        "customs_duty": Decimal("120.00"),
        "other_fees": Decimal("50.00"),
        "notes": "Spring collection pre-order. Expected delivery next week.",
    },
    {
        "tracking_number": "SHP-2025-003",
        "supplier": "Asian Manufacturing Group",
        "status": "pending",
        "date_shipped": None,
        "expected_date": timezone.now().date() + timedelta(days=21),
        "date_received": None,
        "manufacturing_cost": Decimal("3200.00"),
        "shipping_cost": Decimal("420.00"),
        "customs_duty": Decimal("210.00"),
        "other_fees": Decimal("90.00"),
        "notes": "Large order for summer collection. Production started this week.",
    },
]

created_count = 0
for shipment_data in shipments_data:
    # Check if shipment already exists
    if Shipment.objects.filter(tracking_number=shipment_data["tracking_number"]).exists():
        print(f"Shipment {shipment_data['tracking_number']} already exists, skipping...")
        continue

    shipment = Shipment.objects.create(**shipment_data)
    print(f"Created shipment: {shipment.tracking_number}")

    # Add items to each shipment
    for product in products:
        variants = product.variants.all()[:2]  # Get first 2 variants of each product
        for variant in variants:
            quantity = 50 if shipment.status == "delivered" else 75
            received_qty = quantity if shipment.status == "delivered" else 0
            unit_cost = Decimal("12.50") if "shirt" in product.name.lower() else Decimal("18.75")

            ShipmentItem.objects.create(
                shipment=shipment,
                variant=variant,
                quantity=quantity,
                received_quantity=received_qty,
                unit_cost=unit_cost,
            )
            print(f"  Added item: {variant.sku} ({quantity} units @ ${unit_cost})")

    created_count += 1

print(f"\nCreated {created_count} sample shipments with items!")
