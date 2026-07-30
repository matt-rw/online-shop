"""
Stock management admin views — adjustments, counts, and audit log.
"""

import json

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import F, Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from shop.models.inventory import StockAdjustment, StockCount, StockCountItem
from shop.models.product import Product, ProductVariant


@staff_member_required
def inventory_dashboard(request):
    """Stock management — adjustments, physical counts, and audit trail."""

    if request.method == "POST":
        action = request.POST.get("action")

        # Quick adjust a single variant's stock
        if action == "quick_adjust":
            try:
                from shop.utils.stock import adjust_stock
                variant = ProductVariant.objects.get(id=request.POST.get("variant_id"))
                new_qty = int(request.POST.get("new_quantity", 0))
                adj_type = request.POST.get("adjustment_type", "manual")
                reason = request.POST.get("reason", "")

                prev_qty = variant.stock_quantity
                adjust_stock(variant, new_qty, adj_type, reason, request.user)
                diff = new_qty - prev_qty

                return JsonResponse({"success": True, "previous": prev_qty, "new": new_qty, "diff": diff})
            except ProductVariant.DoesNotExist:
                return JsonResponse({"success": False, "error": "Variant not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        # Start a new stock count
        elif action == "start_count":
            try:
                name = request.POST.get("name", "").strip()
                if not name:
                    name = f"Count — {timezone.now().strftime('%b %d, %Y')}"

                count = StockCount.objects.create(
                    name=name,
                    counted_by=request.user,
                )

                # Pre-populate with all active variants
                variants = ProductVariant.objects.filter(
                    is_active=True, product__is_active=True
                ).exclude(product__slug__startswith="test-").select_related("product")

                items = []
                for v in variants:
                    items.append(StockCountItem(
                        stock_count=count,
                        variant=v,
                        system_quantity=v.stock_quantity,
                    ))
                StockCountItem.objects.bulk_create(items)

                return JsonResponse({"success": True, "id": count.id, "items": len(items)})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        # Save a physical count for a variant
        elif action == "save_count_item":
            try:
                item = StockCountItem.objects.get(id=request.POST.get("item_id"))
                physical = int(request.POST.get("physical_quantity", 0))
                item.physical_quantity = physical
                item.difference = physical - item.system_quantity
                item.save(update_fields=["physical_quantity", "difference"])
                return JsonResponse({"success": True, "diff": item.difference})
            except StockCountItem.DoesNotExist:
                return JsonResponse({"success": False, "error": "Item not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        # Apply all corrections from a count
        elif action == "apply_count":
            try:
                from shop.utils.stock import adjust_stock
                count = StockCount.objects.get(id=request.POST.get("count_id"))
                items = count.items.filter(
                    physical_quantity__isnull=False,
                    applied=False,
                ).exclude(difference=0).select_related("variant")

                applied = 0
                for item in items:
                    adjust_stock(
                        item.variant, item.physical_quantity,
                        "count_correction", f"Stock count: {count.name}",
                        request.user,
                    )
                    item.applied = True
                    item.save(update_fields=["applied"])
                    applied += 1

                count.status = "completed"
                count.completed_at = timezone.now()
                count.save()

                return JsonResponse({"success": True, "applied": applied})
            except StockCount.DoesNotExist:
                return JsonResponse({"success": False, "error": "Count not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        # Delete a count
        elif action == "delete_count":
            try:
                count = StockCount.objects.get(id=request.POST.get("count_id"))
                count.delete()
                return JsonResponse({"success": True})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

    # GET — build context
    # All variants with product info
    variants = ProductVariant.objects.filter(
        is_active=True, product__is_active=True
    ).exclude(
        product__slug__startswith="test-"
    ).select_related("product").prefetch_related("attributes__attribute").order_by(
        "product__name", "sku"
    )

    variants_data = []
    for v in variants:
        attrs = []
        for av in v.attributes.select_related("attribute").order_by("attribute__display_order"):
            attrs.append(av.value)
        if not attrs:
            if v.size:
                attrs.append(v.size.code)
            if v.color:
                attrs.append(v.color.name)

        variants_data.append({
            "id": v.id,
            "product": v.product.name,
            "sku": v.sku or "",
            "attrs": " / ".join(attrs),
            "stock": v.stock_quantity,
        })

    # Recent adjustments
    recent_adjustments = StockAdjustment.objects.select_related(
        "variant__product", "adjusted_by"
    )[:30]

    # Active and recent counts
    active_counts = StockCount.objects.filter(status="in_progress").select_related("counted_by")
    completed_counts = StockCount.objects.filter(status="completed").select_related("counted_by")[:10]

    # Active count items (for the first in-progress count)
    active_count_items = []
    active_count = active_counts.first()
    if active_count:
        active_count_items = list(
            active_count.items.select_related("variant__product")
            .prefetch_related("variant__attributes__attribute")
            .order_by("variant__product__name")
        )

    context = {
        "variants_json": json.dumps(variants_data),
        "variants": variants,
        "recent_adjustments": recent_adjustments,
        "active_count": active_count,
        "active_count_items": active_count_items,
        "completed_counts": completed_counts,
        "adjustment_types": StockAdjustment.ADJUSTMENT_TYPES,
    }
    return render(request, "admin/inventory_dashboard.html", context)
