"""
Order management admin views.
"""

import json
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

import pytz

from shop.models import (
    Address,
    Order,
    OrderItem,
    OrderStatus,
    ProductVariant,
)

User = get_user_model()

@staff_member_required
def orders_dashboard(request):
    """
    Orders management dashboard.
    """
    import json

    from django.db.models import Count, Sum
    from django.http import JsonResponse

    from shop.models import Order, OrderItem, OrderStatus

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "update_order_status":
            try:
                order_id = request.POST.get("order_id")
                order = Order.objects.get(id=order_id)
                order.status = request.POST.get("status")
                order.save()
                return JsonResponse({"success": True})
            except Order.DoesNotExist:
                return JsonResponse({"success": False, "error": "Order not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "process_refund":
            try:
                import stripe
                from django.conf import settings
                from shop.models import OrderStatus

                order_id = request.POST.get("order_id")
                order = Order.objects.get(id=order_id)

                # Only paid orders can be refunded
                if order.status != OrderStatus.PAID:
                    return JsonResponse({"success": False, "error": "Only PAID orders can be refunded."})

                # Need a payment intent to refund
                if not order.stripe_payment_intent_id:
                    return JsonResponse({"success": False, "error": "No payment intent found for this order."})

                # Use production Stripe keys
                stripe.api_key = settings.STRIPE_SECRET_KEY

                # Create refund in Stripe
                refund = stripe.Refund.create(
                    payment_intent=order.stripe_payment_intent_id,
                )

                # Update order status
                order.status = OrderStatus.REFUNDED
                order.save()

                return JsonResponse({
                    "success": True,
                    "refund_id": refund.id,
                    "message": f"Refund processed successfully. Order #{order.id} is now REFUNDED.",
                })
            except Order.DoesNotExist:
                return JsonResponse({"success": False, "error": "Order not found"})
            except stripe.StripeError as e:
                return JsonResponse({"success": False, "error": str(e)})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "get_order_items":
            try:
                order_id = request.POST.get("order_id")
                order = Order.objects.get(id=order_id)

                items_data = []
                for item in order.items.select_related("variant", "shipment_item__shipment"):
                    shipment_info = None
                    if item.shipment_item:
                        shipment_info = {
                            "id": item.shipment_item.shipment.id,
                            "tracking": item.shipment_item.shipment.tracking_number,
                            "name": item.shipment_item.shipment.name,
                            "supplier": item.shipment_item.shipment.supplier,
                            "date_received": item.shipment_item.shipment.date_received.isoformat() if item.shipment_item.shipment.date_received else None,
                        }

                    items_data.append({
                        "id": item.id,
                        "sku": item.sku,
                        "variant_name": f"{item.variant.product.name} - {item.variant.size.label if item.variant and item.variant.size else ''} {item.variant.color.name if item.variant and item.variant.color else ''}" if item.variant else item.sku,
                        "quantity": item.quantity,
                        "line_total": float(item.line_total),
                        "unit_cost": float(item.unit_cost) if item.unit_cost else None,
                        "profit": float(item.profit) if item.profit is not None else None,
                        "profit_margin": round(item.profit_margin, 1) if item.profit_margin is not None else None,
                        "shipment": shipment_info,
                    })

                return JsonResponse({"success": True, "items": items_data})
            except Order.DoesNotExist:
                return JsonResponse({"success": False, "error": "Order not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

    # Handle GET request for order details (for editing)
    if request.method == "GET" and request.GET.get("get_order"):
        try:
            order_id = request.GET.get("get_order")
            order = Order.objects.get(id=order_id)

            # Get order items
            items_data = []
            for item in order.items.select_related("variant__product", "variant__size", "variant__color"):
                unit_price = float(item.line_total / item.quantity) if item.quantity > 0 else 0
                items_data.append({
                    "variant_id": item.variant.id if item.variant else None,
                    "product_name": item.variant.product.name if item.variant else item.sku,
                    "display_name": f"{item.variant.product.name} - {item.variant.size.label if item.variant and item.variant.size else ''}" if item.variant else item.sku,
                    "sku": item.sku,
                    "quantity": item.quantity,
                    "unit_price": unit_price,
                    "line_total": float(item.line_total),
                })

            # Get shipping address
            shipping_data = None
            if order.shipping_address:
                shipping_data = {
                    "line1": order.shipping_address.line1,
                    "line2": order.shipping_address.line2,
                    "city": order.shipping_address.city,
                    "region": order.shipping_address.region,
                    "postal_code": order.shipping_address.postal_code,
                    "country": order.shipping_address.country,
                }

            return JsonResponse({
                "success": True,
                "order": {
                    "id": order.id,
                    "customer_name": order.customer_name,
                    "email": order.email,
                    "phone": order.phone,
                    "status": order.status,
                    "subtotal": float(order.subtotal),
                    "tax": float(order.tax),
                    "shipping": float(order.shipping),
                    "total": float(order.total),
                    "created_at": order.created_at.isoformat(),
                    "items": items_data,
                    "shipping_address": shipping_data,
                }
            })
        except Order.DoesNotExist:
            return JsonResponse({"success": False, "error": "Order not found"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    # Check if we should show test orders (hidden by default)
    show_test_orders = request.GET.get("show_test", "false").lower() == "true"

    # Get orders (exclude test orders by default)
    orders = Order.objects.all().select_related("user").prefetch_related("items")
    if not show_test_orders:
        orders = orders.filter(is_test=False)

    # Calculate stats using OrderStatus choices (always exclude test orders from stats)
    from shop.models import OrderStatus

    real_orders = Order.objects.filter(is_test=False)
    stats = {
        "total": real_orders.count(),
        "pending": real_orders.filter(status=OrderStatus.CREATED).count(),
        "processing": real_orders.filter(status=OrderStatus.AWAITING_PAYMENT).count(),
        "shipped": real_orders.filter(status=OrderStatus.SHIPPED).count(),
        "delivered": real_orders.filter(status=OrderStatus.FULFILLED).count(),
        "total_revenue": real_orders.filter(status=OrderStatus.PAID).aggregate(Sum("total"))[
            "total__sum"
        ]
        or 0,
    }

    # Prepare orders data
    orders_data = []
    for order in orders.order_by("-created_at")[:50]:  # Limit to 50 most recent
        # Use customer_name for manual orders, otherwise use user's name
        if order.customer_name:
            user_name = order.customer_name
        elif order.user:
            user_name = f"{order.user.first_name} {order.user.last_name}".strip() or order.user.email
        else:
            user_name = "Guest"

        # Calculate profit for this order
        total_cost = 0
        items_with_cost = 0
        for item in order.items.all():
            if item.unit_cost is not None:
                total_cost += float(item.unit_cost) * item.quantity
                items_with_cost += 1

        profit = float(order.subtotal) - total_cost if items_with_cost > 0 else None

        orders_data.append(
            {
                "id": order.id,
                "order_number": order.order_number,
                "customer_name": user_name,
                "customer_email": order.email or (order.user.email if order.user else ""),
                "customer_phone": order.phone,
                "status": order.status,
                "subtotal": float(order.subtotal),
                "tax": float(order.tax),
                "shipping": float(order.shipping),
                "total": float(order.total),
                "cost": total_cost if items_with_cost > 0 else None,
                "profit": profit,
                "profit_margin": (profit / float(order.subtotal) * 100) if profit and order.subtotal > 0 else None,
                "stripe_payment_intent": order.stripe_payment_intent_id,
                "tracking_number": order.tracking_number,
                "carrier": order.carrier,
                "label_url": order.label_url,
                "created_at": order.created_at.isoformat(),
                "item_count": order.items.count(),
            }
        )

    # Count test orders for the toggle display
    test_orders_count = Order.objects.filter(is_test=True).count()

    context = {
        "orders": orders_data,
        "orders_json": json.dumps(orders_data),
        "stats": stats,
        "show_test_orders": show_test_orders,
        "test_orders_count": test_orders_count,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/orders_dashboard.html", context)


@staff_member_required
def search_variants_for_order(request):
    """
    AJAX endpoint to search products/variants for manual order creation.
    Returns variants with product info, SKU, attributes, price, and stock.
    Supports ?all=true to return all active variants for browsing.
    """
    from django.http import JsonResponse
    from django.db.models import Q
    from shop.models import ProductVariant

    if request.method != "GET":
        return JsonResponse({"error": "Invalid method"}, status=405)

    query = request.GET.get("q", "").strip()
    browse_all = request.GET.get("all", "").lower() == "true"

    try:
        # Base queryset - active variants only
        base_qs = ProductVariant.objects.filter(
            is_active=True,
            product__is_active=True
        ).select_related(
            "product", "size", "color"
        ).order_by("product__name", "sku")

        if browse_all:
            # Return all active variants for browsing
            variants = list(base_qs[:100])
        elif len(query) >= 2:
            # Search by product name or SKU
            variants = list(base_qs.filter(
                Q(product__name__icontains=query) | Q(sku__icontains=query)
            )[:20])
        else:
            return JsonResponse({"results": []})

        results = []
        for variant in variants:
            # Build attribute display string from legacy fields
            attrs = []
            if variant.size:
                attrs.append(f"Size: {variant.size.label or variant.size.code}")
            if variant.color:
                attrs.append(f"Color: {variant.color.name}")

            # Get product image URL (from images JSONField list)
            image_url = None
            if variant.product.images and len(variant.product.images) > 0:
                image_url = variant.product.images[0]

            results.append({
                "id": variant.id,
                "product_name": variant.product.name,
                "sku": variant.sku or f"V-{variant.id}",
                "attributes": ", ".join(attrs),
                "price": float(variant.price),
                "stock": variant.stock_quantity,
                "display_name": f"{variant.product.name} - {', '.join(attrs)}" if attrs else variant.product.name,
                "image_url": image_url,
            })

        print(f"Returning {len(results)} results")  # DEBUG
        return JsonResponse({"results": results})
    except Exception as e:
        import traceback
        print(f"ERROR: {e}")
        print(traceback.format_exc())
        return JsonResponse({"error": str(e)}, status=500)


@staff_member_required
def add_manual_order(request):
    """
    Add a manual order with optional product line items.
    Supports both historical imports (totals only) and new manual orders (with products).
    """
    if request.method == "POST":
        try:
            import json
            from decimal import Decimal
            from datetime import datetime
            from django.http import JsonResponse
            from shop.models import Address, Order, OrderItem, OrderStatus, User, ProductVariant

            # Get form data
            customer_name = request.POST.get("customer_name", "").strip()
            customer_email = request.POST.get("customer_email", "").strip()
            customer_phone = request.POST.get("customer_phone", "").strip()
            order_date = request.POST.get("order_date")
            status = request.POST.get("status", "PAID")
            notes = request.POST.get("notes", "")

            # Get shipping address fields
            shipping_line1 = request.POST.get("shipping_line1", "").strip()
            shipping_line2 = request.POST.get("shipping_line2", "").strip()
            shipping_city = request.POST.get("shipping_city", "").strip()
            shipping_region = request.POST.get("shipping_region", "").strip()
            shipping_postal = request.POST.get("shipping_postal", "").strip()
            shipping_country = request.POST.get("shipping_country", "US").strip()

            # Check if using line items or manual totals
            use_line_items = request.POST.get("use_line_items") == "true"
            line_items_json = request.POST.get("line_items", "[]")
            decrement_stock = request.POST.get("decrement_stock") == "true"

            # Manual orders should NOT auto-link to users
            # They are separate from online orders placed through checkout
            user = None

            # Parse the order date
            order_datetime = timezone.make_aware(
                datetime.strptime(order_date, "%Y-%m-%d")
            )

            # Get discount (applies to both modes)
            discount = Decimal(request.POST.get("discount", "0"))

            if use_line_items:
                # Parse line items and calculate totals
                line_items = json.loads(line_items_json)

                # Check for subtotal override (custom subtotal)
                subtotal_override = request.POST.get("subtotal_override", "").strip()
                if subtotal_override:
                    # Use custom subtotal
                    subtotal = Decimal(subtotal_override)
                elif line_items:
                    # Calculate subtotal from line items
                    subtotal = Decimal("0")
                    for item in line_items:
                        subtotal += Decimal(str(item["price"])) * int(item["quantity"])
                else:
                    return JsonResponse({"success": False, "error": "No line items provided and no subtotal override"})

                tax = Decimal(request.POST.get("tax", "0"))
                shipping = Decimal(request.POST.get("shipping", "0"))
                total = subtotal - discount + tax + shipping
                # Ensure total doesn't go negative
                if total < 0:
                    total = Decimal("0")
            else:
                # Manual totals (historical import)
                subtotal = Decimal(request.POST.get("subtotal", "0"))
                tax = Decimal(request.POST.get("tax", "0"))
                shipping = Decimal(request.POST.get("shipping", "0"))
                total = Decimal(request.POST.get("total", "0"))
                line_items = []

            # Create shipping address if provided
            shipping_address = None
            if shipping_line1 and shipping_city and shipping_postal:
                shipping_address = Address.objects.create(
                    full_name=customer_name or "Customer",
                    line1=shipping_line1,
                    line2=shipping_line2,
                    city=shipping_city,
                    region=shipping_region,
                    postal_code=shipping_postal,
                    country=shipping_country,
                    email=customer_email,
                )

            # Create the order
            order = Order.objects.create(
                user=user,
                customer_name=customer_name,
                email=customer_email,
                phone=customer_phone,
                shipping_address=shipping_address,
                subtotal=subtotal,
                tax=tax,
                shipping=shipping,
                total=total,
                status=status,
                created_at=order_datetime,
                updated_at=timezone.now(),
                stripe_payment_intent_id=f"MANUAL_{order_datetime.strftime('%Y%m%d')}_{timezone.now().strftime('%H%M%S')}",
            )

            # Create OrderItems if line items provided
            for item in line_items:
                variant_id = item.get("variant_id")
                quantity = int(item["quantity"])
                price = Decimal(str(item["price"]))

                variant = None
                sku = item.get("sku", "MANUAL")
                unit_cost = None

                if variant_id:
                    try:
                        variant = ProductVariant.objects.get(id=variant_id)
                        sku = variant.sku or f"V-{variant.id}"
                        unit_cost = variant.cost

                        # Optionally decrement stock
                        if decrement_stock and variant.stock_quantity >= quantity:
                            variant.stock_quantity -= quantity
                            variant.save(update_fields=["stock_quantity"])
                    except ProductVariant.DoesNotExist:
                        pass

                order_item = OrderItem.objects.create(
                    order=order,
                    variant=variant,
                    sku=sku,
                    quantity=quantity,
                    line_total=price * quantity,
                    unit_cost=unit_cost,
                )

                # Try to allocate from shipments for cost tracking
                if variant:
                    order_item.allocate_from_shipments()

            return JsonResponse({
                "success": True,
                "order_id": order.id,
                "message": f"Manual order #{order.id} created successfully",
                "items_created": len(line_items),
            })

        except Exception as e:
            return JsonResponse({
                "success": False,
                "error": str(e)
            })

    return JsonResponse({"success": False, "error": "Invalid request method"})


@staff_member_required
@require_POST
def update_manual_order(request):
    """
    Update an existing manual order.
    """
    try:
        import json
        from decimal import Decimal
        from datetime import datetime
        from django.http import JsonResponse
        from shop.models import Address, Order, OrderItem, OrderStatus, ProductVariant

        order_id = request.POST.get("edit_order_id")
        if not order_id:
            return JsonResponse({"success": False, "error": "No order ID provided"})

        order = Order.objects.get(id=order_id)

        # Only allow editing manual orders
        if not order.stripe_payment_intent_id.startswith("MANUAL_"):
            return JsonResponse({"success": False, "error": "Only manual orders can be edited"})

        # Get form data
        customer_name = request.POST.get("customer_name", "").strip()
        customer_email = request.POST.get("customer_email", "").strip()
        customer_phone = request.POST.get("customer_phone", "").strip()
        order_date = request.POST.get("order_date")
        status = request.POST.get("status", order.status)

        # Get shipping address fields
        shipping_line1 = request.POST.get("shipping_line1", "").strip()
        shipping_line2 = request.POST.get("shipping_line2", "").strip()
        shipping_city = request.POST.get("shipping_city", "").strip()
        shipping_region = request.POST.get("shipping_region", "").strip()
        shipping_postal = request.POST.get("shipping_postal", "").strip()
        shipping_country = request.POST.get("shipping_country", "US").strip()

        # Update basic fields
        order.customer_name = customer_name
        order.email = customer_email
        order.phone = customer_phone
        order.status = status

        # Parse and update order date
        if order_date:
            order_datetime = timezone.make_aware(
                datetime.strptime(order_date, "%Y-%m-%d")
            )
            order.created_at = order_datetime

        # Update or create shipping address
        if shipping_line1 and shipping_city and shipping_postal:
            if order.shipping_address:
                # Update existing
                order.shipping_address.full_name = customer_name or "Customer"
                order.shipping_address.line1 = shipping_line1
                order.shipping_address.line2 = shipping_line2
                order.shipping_address.city = shipping_city
                order.shipping_address.region = shipping_region
                order.shipping_address.postal_code = shipping_postal
                order.shipping_address.country = shipping_country
                order.shipping_address.email = customer_email
                order.shipping_address.save()
            else:
                # Create new
                order.shipping_address = Address.objects.create(
                    full_name=customer_name or "Customer",
                    line1=shipping_line1,
                    line2=shipping_line2,
                    city=shipping_city,
                    region=shipping_region,
                    postal_code=shipping_postal,
                    country=shipping_country,
                    email=customer_email,
                )

        # Handle totals update
        use_line_items = request.POST.get("use_line_items") == "true"
        discount = Decimal(request.POST.get("discount", "0"))
        tax = Decimal(request.POST.get("tax", "0"))
        shipping_cost = Decimal(request.POST.get("shipping", "0"))

        if use_line_items:
            line_items_json = request.POST.get("line_items", "[]")
            line_items = json.loads(line_items_json)

            # Check for subtotal override (custom subtotal)
            subtotal_override = request.POST.get("subtotal_override", "").strip()
            if subtotal_override:
                # Use custom subtotal
                subtotal = Decimal(subtotal_override)
            else:
                # Calculate subtotal from line items
                subtotal = Decimal("0")
                for item in line_items:
                    subtotal += Decimal(str(item["price"])) * int(item["quantity"])

            total = subtotal - discount + tax + shipping_cost
            if total < 0:
                total = Decimal("0")

            order.subtotal = subtotal
            order.tax = tax
            order.shipping = shipping_cost
            order.total = total
        else:
            # Manual totals mode
            order.subtotal = Decimal(request.POST.get("subtotal", str(order.subtotal)))
            order.tax = Decimal(request.POST.get("tax", str(order.tax)))
            order.shipping = Decimal(request.POST.get("shipping", str(order.shipping)))
            order.total = Decimal(request.POST.get("total", str(order.total)))

        order.save()

        return JsonResponse({
            "success": True,
            "order_id": order.id,
            "message": f"Order #{order.id} updated successfully",
        })

    except Order.DoesNotExist:
        return JsonResponse({"success": False, "error": "Order not found"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


def returns_dashboard(request):
    """
    Customer returns management dashboard.
    Supports creating returns, updating status, adding tracking, and processing refunds.
    """
    import json
    from decimal import Decimal

    from django.http import JsonResponse

    from shop.models import (
        Order,
        OrderItem,
        OrderStatus,
        Return,
        ReturnItem,
        ReturnReason,
        ReturnStatus,
    )

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create_return":
            try:
                order_id = request.POST.get("order_id")
                reason = request.POST.get("reason")
                customer_notes = request.POST.get("customer_notes", "")
                item_ids = request.POST.getlist("item_ids")
                quantities = request.POST.getlist("quantities")

                order = Order.objects.get(id=order_id)

                # Create the return
                return_request = Return.objects.create(
                    order=order,
                    reason=reason,
                    customer_notes=customer_notes,
                    status=ReturnStatus.REQUESTED,
                )

                # Create return items
                for item_id, qty in zip(item_ids, quantities):
                    qty = int(qty)
                    if qty > 0:
                        order_item = OrderItem.objects.get(id=item_id)
                        # Calculate refund amount per item
                        unit_price = order_item.line_total / order_item.quantity
                        refund_amount = unit_price * qty
                        ReturnItem.objects.create(
                            return_request=return_request,
                            order_item=order_item,
                            quantity=qty,
                            refund_amount=refund_amount,
                        )

                return JsonResponse({
                    "success": True,
                    "return_id": return_request.id,
                    "message": f"Return #{return_request.id} created successfully.",
                })
            except Order.DoesNotExist:
                return JsonResponse({"success": False, "error": "Order not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_status":
            try:
                return_id = request.POST.get("return_id")
                new_status = request.POST.get("status")

                return_request = Return.objects.get(id=return_id)
                old_status = return_request.status
                return_request.status = new_status

                # Set timestamps based on status transitions
                if new_status == ReturnStatus.APPROVED and old_status != ReturnStatus.APPROVED:
                    return_request.approved_at = timezone.now()
                elif new_status == ReturnStatus.RECEIVED and old_status != ReturnStatus.RECEIVED:
                    return_request.received_at = timezone.now()
                    # Mark all items as received
                    return_request.items.update(received=True)
                elif new_status == ReturnStatus.REFUNDED and old_status != ReturnStatus.REFUNDED:
                    return_request.refunded_at = timezone.now()

                return_request.save()

                return JsonResponse({
                    "success": True,
                    "message": f"Return #{return_id} status updated to {new_status}.",
                })
            except Return.DoesNotExist:
                return JsonResponse({"success": False, "error": "Return not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "add_tracking":
            try:
                return_id = request.POST.get("return_id")
                tracking_number = request.POST.get("tracking_number")
                carrier = request.POST.get("carrier")

                return_request = Return.objects.get(id=return_id)
                return_request.tracking_number = tracking_number
                return_request.carrier = carrier

                # Optionally update status to IN_TRANSIT
                if return_request.status in [ReturnStatus.APPROVED, ReturnStatus.AWAITING_SHIPMENT]:
                    return_request.status = ReturnStatus.IN_TRANSIT

                return_request.save()

                return JsonResponse({
                    "success": True,
                    "message": f"Tracking info added to Return #{return_id}.",
                })
            except Return.DoesNotExist:
                return JsonResponse({"success": False, "error": "Return not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "generate_label":
            try:
                import easypost
                from django.conf import settings

                return_id = request.POST.get("return_id")
                return_request = Return.objects.get(id=return_id)
                order = return_request.order

                if not order.shipping_address:
                    return JsonResponse({"success": False, "error": "Order has no shipping address"})

                # Initialize EasyPost
                client = easypost.EasyPostClient(settings.EASYPOST_API_KEY)

                # Create return shipment (swap from/to addresses)
                # Customer is sending back to us
                from_address = client.address.create(
                    name=order.shipping_address.full_name,
                    street1=order.shipping_address.line1,
                    street2=order.shipping_address.line2 or "",
                    city=order.shipping_address.city,
                    state=order.shipping_address.region,
                    zip=order.shipping_address.postal_code,
                    country=order.shipping_address.country,
                )

                # Our return address (from site settings or default)
                to_address = client.address.create(
                    company="Blueprint Apparel",
                    street1="123 Main St",
                    city="Austin",
                    state="TX",
                    zip="78701",
                    country="US",
                )

                # Create parcel (default small package)
                parcel = client.parcel.create(
                    length=10,
                    width=8,
                    height=4,
                    weight=16,
                )

                # Create shipment
                shipment = client.shipment.create(
                    from_address=from_address,
                    to_address=to_address,
                    parcel=parcel,
                    is_return=True,
                )

                # Buy cheapest rate
                lowest_rate = shipment.lowest_rate()
                bought_shipment = client.shipment.buy(shipment.id, rate=lowest_rate)

                # Update return with tracking info
                return_request.tracking_number = bought_shipment.tracking_code
                return_request.carrier = lowest_rate.carrier
                return_request.return_label_url = bought_shipment.postage_label.label_url
                return_request.status = ReturnStatus.AWAITING_SHIPMENT
                return_request.save()

                return JsonResponse({
                    "success": True,
                    "tracking_number": bought_shipment.tracking_code,
                    "carrier": lowest_rate.carrier,
                    "label_url": bought_shipment.postage_label.label_url,
                    "cost": str(lowest_rate.rate),
                    "message": f"Return label generated. Cost: ${lowest_rate.rate}",
                })
            except Return.DoesNotExist:
                return JsonResponse({"success": False, "error": "Return not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "mark_item_received":
            try:
                return_item_id = request.POST.get("return_item_id")
                condition_notes = request.POST.get("condition_notes", "")

                return_item = ReturnItem.objects.get(id=return_item_id)
                return_item.received = True
                return_item.condition_notes = condition_notes
                return_item.save()

                # Check if all items received
                return_request = return_item.return_request
                if return_request.all_items_received:
                    return_request.status = ReturnStatus.RECEIVED
                    return_request.received_at = timezone.now()
                    return_request.save()

                return JsonResponse({
                    "success": True,
                    "all_received": return_request.all_items_received,
                    "message": f"Item marked as received.",
                })
            except ReturnItem.DoesNotExist:
                return JsonResponse({"success": False, "error": "Return item not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "process_refund":
            try:
                import stripe
                from django.conf import settings

                return_id = request.POST.get("return_id")
                custom_amount = request.POST.get("refund_amount")

                return_request = Return.objects.get(id=return_id)
                order = return_request.order

                if not order.stripe_payment_intent_id:
                    return JsonResponse({"success": False, "error": "No payment intent found for this order."})

                # Calculate refund amount
                if custom_amount:
                    refund_amount = Decimal(custom_amount)
                else:
                    refund_amount = return_request.total_refund_amount

                # Convert to cents for Stripe
                refund_amount_cents = int(refund_amount * 100)

                # Initialize Stripe
                stripe.api_key = settings.STRIPE_SECRET_KEY

                # Create refund
                refund = stripe.Refund.create(
                    payment_intent=order.stripe_payment_intent_id,
                    amount=refund_amount_cents,
                )

                # Update return
                return_request.refund_amount = refund_amount
                return_request.stripe_refund_id = refund.id
                return_request.status = ReturnStatus.REFUNDED
                return_request.refunded_at = timezone.now()
                return_request.save()

                return JsonResponse({
                    "success": True,
                    "refund_id": refund.id,
                    "amount": str(refund_amount),
                    "message": f"Refund of ${refund_amount} processed successfully.",
                })
            except Return.DoesNotExist:
                return JsonResponse({"success": False, "error": "Return not found"})
            except stripe.StripeError as e:
                return JsonResponse({"success": False, "error": str(e)})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "add_notes":
            try:
                return_id = request.POST.get("return_id")
                admin_notes = request.POST.get("admin_notes")

                return_request = Return.objects.get(id=return_id)
                return_request.admin_notes = admin_notes
                return_request.save()

                return JsonResponse({
                    "success": True,
                    "message": "Notes saved.",
                })
            except Return.DoesNotExist:
                return JsonResponse({"success": False, "error": "Return not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "get_order_items":
            try:
                order_id = request.POST.get("order_id")
                order = Order.objects.get(id=order_id)

                items_data = []
                for item in order.items.select_related("variant", "variant__product"):
                    product_name = ""
                    if item.variant and item.variant.product:
                        product_name = item.variant.product.name
                    items_data.append({
                        "id": item.id,
                        "sku": item.sku,
                        "product_name": product_name,
                        "quantity": item.quantity,
                        "line_total": str(item.line_total),
                        "unit_price": str(item.line_total / item.quantity) if item.quantity > 0 else "0",
                    })

                return JsonResponse({
                    "success": True,
                    "items": items_data,
                })
            except Order.DoesNotExist:
                return JsonResponse({"success": False, "error": "Order not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

    # GET request - display dashboard
    returns = Return.objects.select_related("order").prefetch_related(
        "items__order_item__variant__product"
    ).all()

    # Get orders for create return dropdown (paid, shipped, or fulfilled orders)
    eligible_orders = Order.objects.filter(
        status__in=[OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.FULFILLED]
    ).order_by("-created_at")[:100]

    # Build return data for template
    returns_data = []
    for r in returns:
        items_list = []
        for item in r.items.all():
            product_name = ""
            if item.order_item.variant and item.order_item.variant.product:
                product_name = item.order_item.variant.product.name
            items_list.append({
                "id": item.id,
                "sku": item.order_item.sku,
                "product_name": product_name,
                "quantity": item.quantity,
                "refund_amount": str(item.refund_amount),
                "received": item.received,
                "condition_notes": item.condition_notes,
            })

        returns_data.append({
            "id": r.id,
            "order_id": r.order_id,
            "order_number": r.order.order_number,
            "status": r.status,
            "reason": r.reason,
            "reason_display": r.get_reason_display(),
            "customer_notes": r.customer_notes,
            "admin_notes": r.admin_notes,
            "tracking_number": r.tracking_number,
            "carrier": r.carrier,
            "return_label_url": r.return_label_url,
            "refund_amount": str(r.refund_amount) if r.refund_amount else None,
            "total_refund_amount": str(r.total_refund_amount),
            "stripe_refund_id": r.stripe_refund_id,
            "created_at": r.created_at.isoformat(),
            "approved_at": r.approved_at.isoformat() if r.approved_at else None,
            "received_at": r.received_at.isoformat() if r.received_at else None,
            "refunded_at": r.refunded_at.isoformat() if r.refunded_at else None,
            "items": items_list,
            "all_items_received": r.all_items_received,
            "customer_email": r.order.email,
        })

    # Calculate stats
    stats = {
        "total": returns.count(),
        "requested": returns.filter(status=ReturnStatus.REQUESTED).count(),
        "approved": returns.filter(status=ReturnStatus.APPROVED).count(),
        "awaiting_shipment": returns.filter(status=ReturnStatus.AWAITING_SHIPMENT).count(),
        "in_transit": returns.filter(status=ReturnStatus.IN_TRANSIT).count(),
        "received": returns.filter(status=ReturnStatus.RECEIVED).count(),
        "refunded": returns.filter(status=ReturnStatus.REFUNDED).count(),
    }

    # Prepare orders for dropdown
    orders_data = []
    for order in eligible_orders:
        orders_data.append({
            "id": order.id,
            "order_number": order.order_number,
            "email": order.email,
            "total": str(order.total),
            "status": order.status,
            "created_at": order.created_at.strftime("%b %d, %Y"),
        })

    context = {
        "returns": returns_data,
        "returns_json": json.dumps(returns_data),
        "orders": orders_data,
        "orders_json": json.dumps(orders_data),
        "stats": stats,
        "return_statuses": ReturnStatus.choices,
        "return_reasons": ReturnReason.choices,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/returns_dashboard.html", context)

@staff_member_required
def generate_shipping_label(request, order_id):
    """
    Auto-generate shipping label using cheapest rate from EasyPost.
    """
    from django.http import JsonResponse

    from shop.models import Order
    from shop.utils.shipping_helper import create_shipping_label, get_shipping_rates

    try:
        order = Order.objects.get(id=order_id)

        # Get all available rates
        rates = get_shipping_rates(order)

        if not rates:
            return JsonResponse(
                {"success": False, "error": "No shipping rates available. Check EasyPost configuration."},
                status=400,
            )

        # Use cheapest rate
        cheapest_rate = rates[0]

        # Create label
        result = create_shipping_label(order, cheapest_rate["id"], cheapest_rate["provider"])

        return JsonResponse(
            {
                "success": True,
                "tracking_number": result["tracking_number"],
                "carrier": result["carrier"],
                "label_url": result["label_url"],
                "cost": result["cost"],
            }
        )

    except Order.DoesNotExist:
        return JsonResponse({"success": False, "error": "Order not found"}, status=404)
    except Exception as e:
        logger.error(f"Error generating shipping label: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@staff_member_required
def manual_tracking(request, order_id):
    """
    Manually enter tracking information (for Pirate Ship, etc.).
    """
    from django.http import JsonResponse

    from shop.models import Order
    from shop.utils.shipping_helper import manual_tracking_entry

    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST required"}, status=405)

    try:
        order = Order.objects.get(id=order_id)

        tracking_number = request.POST.get("tracking_number", "").strip()
        carrier = request.POST.get("carrier", "").strip()

        if not tracking_number or not carrier:
            return JsonResponse(
                {"success": False, "error": "Tracking number and carrier are required"}, status=400
            )

        result = manual_tracking_entry(order, tracking_number, carrier)

        return JsonResponse(
            {
                "success": True,
                "tracking_number": result["tracking_number"],
                "carrier": result["carrier"],
            }
        )

    except Order.DoesNotExist:
        return JsonResponse({"success": False, "error": "Order not found"}, status=404)
    except Exception as e:
        logger.error(f"Error saving manual tracking: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


