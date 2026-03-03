"""
Inventory and shipment management admin views.
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, F, Q, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

import pytz

from shop.models import (
    Product,
    ProductVariant,
    Shipment,
    ShipmentItem,
    Size,
)

def shipments_dashboard(request):
    """
    Shipments tracking dashboard for incoming inventory.
    """
    import json
    from datetime import date

    from django.http import JsonResponse

    from shop.models import Shipment

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create_shipment":
            import json as json_module
            import uuid
            from datetime import timedelta
            from decimal import Decimal

            from shop.models import ProductVariant, ShipmentItem

            try:
                tracking_number = request.POST.get("tracking_number", "").strip()
                supplier = request.POST.get("supplier", "").strip()
                expected_date = request.POST.get("expected_date")

                # Auto-generate tracking number if not provided
                if not tracking_number:
                    tracking_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"

                # Default expected date to 2 weeks if not provided
                if not expected_date:
                    expected_date = (timezone.now().date() + timedelta(days=14)).isoformat()

                shipment = Shipment.objects.create(
                    name=request.POST.get("name", "").strip(),
                    tracking_number=tracking_number,
                    supplier=supplier or "Unknown Supplier",
                    status=request.POST.get("status") or "pending",
                    date_shipped=request.POST.get("date_shipped") or None,
                    expected_date=expected_date,
                    date_received=request.POST.get("date_received") or None,
                    manufacturing_cost=request.POST.get("manufacturing_cost") or 0,
                    shipping_cost=request.POST.get("shipping_cost") or 0,
                    customs_duty=request.POST.get("customs_duty") or 0,
                    other_fees=request.POST.get("other_fees") or 0,
                    notes=request.POST.get("notes", ""),
                )

                # Create shipment items if provided
                new_items_json = request.POST.get("new_items", "[]")
                new_items = json_module.loads(new_items_json)

                for item_data in new_items:
                    variant_id = item_data.get("variant_id")
                    quantity = int(item_data.get("quantity", 0))
                    unit_cost = item_data.get("unit_cost")

                    if quantity <= 0:
                        continue

                    variant = ProductVariant.objects.select_related("product").get(id=variant_id)

                    # Use provided cost or auto-populate from variant/product
                    if unit_cost is not None and str(unit_cost).strip():
                        final_cost = Decimal(str(unit_cost))
                    elif variant.cost is not None:
                        final_cost = variant.cost
                    else:
                        final_cost = variant.product.base_cost or Decimal("0")

                    # If shipment is delivered, set received_quantity = quantity
                    received_qty = quantity if shipment.status == "delivered" else 0

                    ShipmentItem.objects.create(
                        shipment=shipment,
                        variant=variant,
                        quantity=quantity,
                        received_quantity=received_qty,
                        unit_cost=final_cost,
                    )

                    # If delivered, also update variant stock
                    if shipment.status == "delivered" and received_qty > 0:
                        variant.stock_quantity += received_qty
                        variant.save(update_fields=["stock_quantity"])

                return JsonResponse({
                    "success": True,
                    "shipment_id": shipment.id,
                    "tracking_number": shipment.tracking_number,
                })
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_shipment":
            try:
                from shop.models import ShipmentItem

                shipment_id = request.POST.get("shipment_id")
                shipment = Shipment.objects.get(id=shipment_id)

                # Track old status to detect delivery
                old_status = shipment.status
                new_status = request.POST.get("status")

                shipment.name = request.POST.get("name", "").strip()
                shipment.tracking_number = request.POST.get("tracking_number")
                shipment.supplier = request.POST.get("supplier")
                shipment.status = new_status
                shipment.date_shipped = request.POST.get("date_shipped") or None
                shipment.expected_date = request.POST.get("expected_date")
                shipment.date_received = request.POST.get("date_received") or None
                shipment.manufacturing_cost = request.POST.get("manufacturing_cost") or 0
                shipment.shipping_cost = request.POST.get("shipping_cost") or 0
                shipment.customs_duty = request.POST.get("customs_duty") or 0
                shipment.other_fees = request.POST.get("other_fees") or 0
                shipment.notes = request.POST.get("notes", "")

                # Set date received if status is delivered and not already set
                if shipment.status == "delivered" and not shipment.date_received:
                    shipment.date_received = date.today()

                shipment.save()

                # If status changed TO delivered, add received quantities to variant stock
                if old_status != "delivered" and new_status == "delivered":
                    for item in shipment.items.select_related("variant"):
                        # Use received_quantity if set, otherwise default to quantity
                        qty_to_add = item.received_quantity if item.received_quantity > 0 else item.quantity
                        if qty_to_add > 0:
                            # If received_quantity wasn't set, update it to match quantity
                            if item.received_quantity == 0:
                                item.received_quantity = item.quantity
                                item.save(update_fields=["received_quantity"])
                            item.variant.stock_quantity += qty_to_add
                            item.variant.save(update_fields=["stock_quantity"])

                # If status changed FROM delivered to something else, reverse the stock
                elif old_status == "delivered" and new_status != "delivered":
                    for item in shipment.items.select_related("variant"):
                        qty_to_remove = item.received_quantity if item.received_quantity > 0 else item.quantity
                        if qty_to_remove > 0:
                            item.variant.stock_quantity = max(0, item.variant.stock_quantity - qty_to_remove)
                            item.variant.save(update_fields=["stock_quantity"])

                # Update shipment items
                for key, value in request.POST.items():
                    if key.startswith("item_") and "_quantity" in key:
                        item_id = key.split("_")[1]
                        try:
                            item = ShipmentItem.objects.get(id=item_id, shipment=shipment)
                            if key.endswith("_quantity"):
                                item.quantity = value
                            elif key.endswith("_received_quantity"):
                                item.received_quantity = value
                        except ShipmentItem.DoesNotExist:
                            pass
                    elif key.startswith("item_") and "_unit_cost" in key:
                        item_id = key.split("_")[1]
                        try:
                            item = ShipmentItem.objects.get(id=item_id, shipment=shipment)
                            item.unit_cost = value
                            item.save()
                        except ShipmentItem.DoesNotExist:
                            pass

                # Save all items
                for item in shipment.items.all():
                    quantity_key = f"item_{item.id}_quantity"
                    received_key = f"item_{item.id}_received_quantity"
                    cost_key = f"item_{item.id}_unit_cost"

                    if quantity_key in request.POST:
                        item.quantity = request.POST.get(quantity_key)
                    if received_key in request.POST:
                        item.received_quantity = request.POST.get(received_key)
                    if cost_key in request.POST:
                        item.unit_cost = request.POST.get(cost_key)
                    item.save()

                return JsonResponse({"success": True})
            except Shipment.DoesNotExist:
                return JsonResponse({"success": False, "error": "Shipment not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_shipment_item":
            try:
                from shop.models import ShipmentItem

                item_id = request.POST.get("item_id")
                item = ShipmentItem.objects.get(id=item_id)

                item.quantity = request.POST.get("quantity")
                item.received_quantity = request.POST.get("received_quantity")
                item.unit_cost = request.POST.get("unit_cost")

                item.save()
                return JsonResponse({"success": True})
            except ShipmentItem.DoesNotExist:
                return JsonResponse({"success": False, "error": "Shipment item not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "add_shipment_item":
            try:
                from shop.models import ProductVariant, ShipmentItem

                shipment_id = request.POST.get("shipment_id")
                variant_id = request.POST.get("variant_id")
                quantity = request.POST.get("quantity", 0)
                unit_cost = request.POST.get("unit_cost", 0)

                shipment = Shipment.objects.get(id=shipment_id)
                variant = ProductVariant.objects.get(id=variant_id)

                # Check if this variant already exists in the shipment
                existing_item = ShipmentItem.objects.filter(
                    shipment=shipment, variant=variant
                ).first()

                if existing_item:
                    # Add to existing quantity instead of erroring
                    existing_item.quantity += int(quantity)
                    # Update cost if provided (use new cost for the additional quantity)
                    if unit_cost:
                        existing_item.unit_cost = unit_cost
                    existing_item.save()
                    item = existing_item
                    was_updated = True
                else:
                    item = ShipmentItem.objects.create(
                        shipment=shipment,
                        variant=variant,
                        quantity=quantity,
                        received_quantity=0,
                        unit_cost=unit_cost,
                    )
                    was_updated = False

                return JsonResponse(
                    {
                        "success": True,
                        "updated": was_updated,
                        "item": {
                            "id": item.id,
                            "variant_id": variant.id,
                            "variant_sku": variant.sku,
                            "variant_name": f"{variant.product.name} - {variant.size.label if variant.size else ''} {variant.color.name if variant.color else ''}",
                            "quantity": item.quantity,
                            "received_quantity": item.received_quantity,
                            "unit_cost": float(item.unit_cost),
                            "total_cost": float(item.total_cost),
                        },
                    }
                )
            except Shipment.DoesNotExist:
                return JsonResponse({"success": False, "error": "Shipment not found"})
            except ProductVariant.DoesNotExist:
                return JsonResponse({"success": False, "error": "Variant not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "bulk_add_shipment_items":
            # Add multiple variants at once from matrix UI
            try:
                import json as json_module

                from decimal import Decimal

                from shop.models import ProductVariant, ShipmentItem

                items_json = request.POST.get("items", "[]")
                items_to_add = json_module.loads(items_json)

                if not items_to_add:
                    return JsonResponse({"success": False, "error": "No items to add"})

                added_items = []
                for item_data in items_to_add:
                    variant_id = item_data.get("variant_id")
                    quantity = int(item_data.get("quantity", 0))
                    unit_cost = item_data.get("unit_cost")

                    if quantity <= 0:
                        continue

                    variant = ProductVariant.objects.select_related("product").get(id=variant_id)

                    # Auto-populate unit_cost from variant cost or product base_cost if not provided
                    if unit_cost is not None and str(unit_cost).strip():
                        final_cost = Decimal(str(unit_cost))
                    elif variant.cost is not None:
                        final_cost = variant.cost
                    else:
                        final_cost = variant.product.base_cost or Decimal("0")

                    size_label = variant.size.label if variant.size else ""
                    color_name = variant.color.name if variant.color else ""

                    added_items.append({
                        "id": None,
                        "variant_id": variant.id,
                        "variant_sku": variant.sku,
                        "variant_name": f"{variant.product.name} - {size_label} {color_name}".strip(),
                        "quantity": quantity,
                        "received_quantity": 0,
                        "unit_cost": float(final_cost),
                        "total_cost": float(quantity * final_cost),
                    })

                return JsonResponse({"success": True, "items": added_items})

            except ProductVariant.DoesNotExist:
                return JsonResponse({"success": False, "error": "Variant not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "delete_shipment_item":
            try:
                from shop.models import ShipmentItem

                item_id = request.POST.get("item_id")
                item = ShipmentItem.objects.get(id=item_id)
                item.delete()

                return JsonResponse({"success": True})
            except ShipmentItem.DoesNotExist:
                return JsonResponse({"success": False, "error": "Shipment item not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "delete_shipment":
            try:
                from shop.models import ShipmentItem

                shipment_id = request.POST.get("shipment_id")
                shipment = Shipment.objects.get(id=shipment_id)

                # If delivered, subtract stock from variants
                if shipment.status == "delivered":
                    items = ShipmentItem.objects.filter(shipment=shipment).select_related("variant")
                    for item in items:
                        variant = item.variant
                        # Subtract received quantity (use received_quantity if set, else quantity)
                        qty_to_subtract = item.received_quantity if item.received_quantity > 0 else item.quantity
                        variant.stock_quantity = max(0, variant.stock_quantity - qty_to_subtract)
                        variant.save(update_fields=["stock_quantity"])

                shipment.delete()
                return JsonResponse({"success": True})
            except Shipment.DoesNotExist:
                return JsonResponse({"success": False, "error": "Shipment not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

    # Get all shipments
    shipments = Shipment.objects.all()

    # Calculate stats
    stats = {
        "pending": shipments.filter(status="pending").count(),
        "in_transit": shipments.filter(status="in-transit").count(),
        "delivered": shipments.filter(status="delivered").count(),
        "delayed": shipments.filter(status="delayed").count(),
    }

    # Calculate metrics
    from django.db.models import Avg

    # Average shipping time (days from shipped to received)
    delivered_shipments = shipments.filter(
        status="delivered", date_shipped__isnull=False, date_received__isnull=False
    )
    avg_shipping_days = 0
    if delivered_shipments.exists():
        total_days = 0
        count = 0
        for ship in delivered_shipments:
            if ship.date_shipped and ship.date_received:
                days = (ship.date_received - ship.date_shipped).days
                total_days += days
                count += 1
        avg_shipping_days = round(total_days / count, 1) if count > 0 else 0

    # Average costs across all shipments
    metrics = {
        "avg_shipping_days": avg_shipping_days,
        "avg_manufacturing_cost": shipments.aggregate(avg=Avg("manufacturing_cost"))["avg"] or 0,
        "avg_shipping_cost": shipments.aggregate(avg=Avg("shipping_cost"))["avg"] or 0,
        "avg_customs_duty": shipments.aggregate(avg=Avg("customs_duty"))["avg"] or 0,
        "avg_other_fees": shipments.aggregate(avg=Avg("other_fees"))["avg"] or 0,
    }

    # Prepare data for template and JSON
    shipments_data = []
    for shipment in shipments:
        # Get items for this shipment
        items_data = []
        for item in shipment.items.all():
            # Calculate stock impact for deletion warning
            qty_received = item.received_quantity if item.received_quantity > 0 else item.quantity
            current_stock = item.variant.stock_quantity
            stock_after_delete = current_stock - qty_received if shipment.status == "delivered" else current_stock

            items_data.append(
                {
                    "id": item.id,
                    "variant_id": item.variant.id,
                    "variant_sku": item.variant.sku,
                    "variant_name": f"{item.variant.product.name} - {item.variant.size.label if item.variant.size else ''} {item.variant.color.name if item.variant.color else ''}",
                    "quantity": item.quantity,
                    "received_quantity": item.received_quantity,
                    "sold_quantity": item.sold_quantity,
                    "available_quantity": item.available_quantity,
                    "unit_cost": float(item.unit_cost),
                    "total_cost": float(item.total_cost),
                    "current_stock": current_stock,
                    "stock_after_delete": max(0, stock_after_delete),
                    "would_go_negative": stock_after_delete < 0,
                }
            )

        shipments_data.append(
            {
                "id": shipment.id,
                "name": shipment.name,
                "tracking_number": shipment.tracking_number,
                "supplier": shipment.supplier,
                "status": shipment.status,
                "date_shipped": (
                    shipment.date_shipped.isoformat() if shipment.date_shipped else None
                ),
                "expected_date": shipment.expected_date.isoformat(),
                "date_received": (
                    shipment.date_received.isoformat() if shipment.date_received else None
                ),
                "manufacturing_cost": float(shipment.manufacturing_cost),
                "shipping_cost": float(shipment.shipping_cost),
                "customs_duty": float(shipment.customs_duty),
                "other_fees": float(shipment.other_fees),
                "total_cost": float(shipment.total_cost),
                "item_count": shipment.item_count,
                "variant_count": shipment.variant_count,
                "items": items_data,
                "notes": shipment.notes,
            }
        )

    # Get all product variants for the variant selector
    from shop.models import Product, ProductVariant

    all_variants = ProductVariant.objects.select_related(
        "product", "size", "color"
    ).all()

    variants_data = []
    for variant in all_variants:
        size_label = variant.size.label if variant.size else ""
        color_name = variant.color.name if variant.color else ""
        variant_display = f"{variant.product.name} - {size_label} {color_name}".strip()

        variants_data.append(
            {
                "id": variant.id,
                "sku": variant.sku,
                "display_name": variant_display,
                "product_name": variant.product.name,
                "product_id": variant.product.id,
                "size": size_label,
                "color": color_name,
                "cost": float(variant.cost) if variant.cost else None,
            }
        )

    # Get products with variants grouped for matrix view
    products_for_matrix = []
    all_products = Product.objects.prefetch_related(
        "variants__size", "variants__color"
    ).filter(variants__isnull=False).distinct()

    for product in all_products:
        # Get all sizes and colors for this product
        sizes = set()
        colors = set()
        variants_map = {}

        for variant in product.variants.all():
            size_label = variant.size.label if variant.size else "One Size"
            color_name = variant.color.name if variant.color else "Default"
            sizes.add(size_label)
            colors.add(color_name)
            # Map (size, color) -> variant data
            key = f"{size_label}|{color_name}"
            variants_map[key] = {
                "id": variant.id,
                "sku": variant.sku,
                "cost": float(variant.cost) if variant.cost else float(product.base_cost or 0),
                "stock": variant.stock_quantity,
            }

        products_for_matrix.append({
            "id": product.id,
            "name": product.name,
            "base_cost": float(product.base_cost or 0),
            "sizes": sorted(list(sizes)),
            "colors": sorted(list(colors)),
            "variants": variants_map,
        })

    # Get unique suppliers for autocomplete
    saved_suppliers = list(
        Shipment.objects.exclude(supplier="")
        .exclude(supplier="Unknown Supplier")
        .values_list("supplier", flat=True)
        .distinct()
        .order_by("supplier")
    )

    context = {
        "shipments": shipments_data,
        "shipments_json": json.dumps(shipments_data, default=str),
        "variants": variants_data,
        "variants_json": json.dumps(variants_data, default=str),
        "products_for_matrix": products_for_matrix,
        "products_for_matrix_json": json.dumps(products_for_matrix, default=str),
        "saved_suppliers": saved_suppliers,
        "saved_suppliers_json": json.dumps(saved_suppliers),
        "stats": stats,
        "metrics": metrics,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/shipments_dashboard.html", context)

