"""
Test center and checkout testing admin views.
"""

import json
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

import pytz
import stripe

from shop.decorators import two_factor_required
from shop.models import (
    Cart,
    CartItem,
    Order,
    OrderItem,
    Product,
    ProductVariant,
    SiteSettings,
)
from shop.models.settings import SiteSettings

@staff_member_required
@two_factor_required
def test_center(request):
    """
    Test Center for testing Stripe purchases, discounts, and refunds.
    Uses Stripe test keys to create real test transactions.
    """
    from decimal import Decimal

    import stripe
    from django.conf import settings

    from shop.models import Discount, Order, OrderStatus, Product

    # Check if test keys are configured
    test_secret_key = settings.STRIPE_TEST_SECRET_KEY
    test_publishable_key = settings.STRIPE_TEST_PUBLISHABLE_KEY
    test_keys_configured = bool(test_secret_key and test_publishable_key)

    # If test keys not configured, render page with message instead of redirecting
    if not test_keys_configured:
        context = {
            "test_orders": [],
            "test_orders_json": "[]",
            "products": [],
            "test_products": [],
            "discounts": [],
            "stripe_publishable_key": "",
            "test_keys_configured": False,
            "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
        }
        return render(request, "admin/test_center.html", context)

    # Use test keys for all Stripe operations in this view
    stripe.api_key = test_secret_key

    # Get test orders
    test_orders = Order.objects.filter(is_test=True).order_by("-created_at")[:20]

    # Get products for the dropdown
    products = Product.objects.filter(is_active=True).order_by("name")

    # Get active discount codes
    discounts = Discount.objects.filter(is_active=True).order_by("name")

    # Handle POST actions
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create_test_order":
            try:
                amount = Decimal(request.POST.get("amount", "10.00"))
                product_id = request.POST.get("product_id")
                description = request.POST.get("description", "Test order")
                auto_pay = request.POST.get("auto_pay") == "true"
                payment_method = request.POST.get("payment_method", "pm_card_visa")

                # Create Stripe PaymentIntent
                intent_params = {
                    "amount": int(amount * 100),  # Convert to cents
                    "currency": "usd",
                    "description": f"Test Center: {description}",
                    "metadata": {
                        "test_center": "true",
                        "product_id": product_id or "",
                    },
                    "payment_method_types": ["card"],  # Only accept cards, no redirects
                }

                # If auto_pay, use a test payment method and confirm immediately
                if auto_pay:
                    intent_params["payment_method"] = payment_method
                    intent_params["confirm"] = True

                intent = stripe.PaymentIntent.create(**intent_params)

                # Determine order status based on payment
                if auto_pay and intent.status == "succeeded":
                    order_status = OrderStatus.PAID
                else:
                    order_status = OrderStatus.AWAITING_PAYMENT

                # Create test order
                order = Order.objects.create(
                    email="test@testcenter.local",
                    status=order_status,
                    subtotal=amount,
                    shipping=Decimal("0.00"),
                    tax=Decimal("0.00"),
                    total=amount,
                    stripe_payment_intent_id=intent.id,
                    is_test=True,
                )

                if auto_pay and intent.status == "succeeded":
                    return JsonResponse({
                        "success": True,
                        "auto_paid": True,
                        "order_id": order.id,
                        "payment_intent_id": intent.id,
                        "message": f"Test order #{order.id} created and paid!",
                    })
                else:
                    return JsonResponse({
                        "success": True,
                        "auto_paid": False,
                        "order_id": order.id,
                        "payment_intent_id": intent.id,
                        "client_secret": intent.client_secret,
                        "message": f"Test order #{order.id} created. Use Stripe test card to complete payment.",
                    })

            except stripe.StripeError as e:
                # For card errors, extract the user-friendly message
                error_msg = str(e)
                if hasattr(e, 'user_message'):
                    error_msg = e.user_message
                return JsonResponse({"success": False, "error": error_msg, "declined": True})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "confirm_test_payment":
            try:
                payment_intent_id = request.POST.get("payment_intent_id")
                order_id = request.POST.get("order_id")

                # Retrieve the PaymentIntent to check status
                intent = stripe.PaymentIntent.retrieve(payment_intent_id)

                order = Order.objects.get(id=order_id, is_test=True)

                if intent.status == "succeeded":
                    order.status = OrderStatus.PAID
                    order.save()
                    return JsonResponse({
                        "success": True,
                        "message": f"Payment confirmed! Order #{order.id} is now PAID.",
                    })
                else:
                    return JsonResponse({
                        "success": False,
                        "error": f"Payment not yet succeeded. Status: {intent.status}",
                    })

            except Order.DoesNotExist:
                return JsonResponse({"success": False, "error": "Test order not found"})
            except stripe.StripeError as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "apply_discount":
            try:
                discount_code = request.POST.get("discount_code", "").strip().upper()
                cart_total = Decimal(request.POST.get("cart_total", "100.00"))

                # Find the discount
                try:
                    discount = Discount.objects.get(code__iexact=discount_code, is_active=True)
                except Discount.DoesNotExist:
                    return JsonResponse({"success": False, "error": f"Discount code '{discount_code}' not found or inactive."})

                # Check validity
                now = timezone.now()
                if discount.valid_from > now:
                    return JsonResponse({"success": False, "error": "Discount code is not yet active."})
                if discount.valid_until and discount.valid_until < now:
                    return JsonResponse({"success": False, "error": "Discount code has expired."})
                if discount.min_purchase_amount and cart_total < discount.min_purchase_amount:
                    return JsonResponse({
                        "success": False,
                        "error": f"Minimum purchase of ${discount.min_purchase_amount} required."
                    })
                if discount.max_uses and discount.times_used >= discount.max_uses:
                    return JsonResponse({"success": False, "error": "Discount code has reached its usage limit."})

                # Calculate discount
                if discount.discount_type == "percentage":
                    discount_amount = cart_total * (discount.value / 100)
                    discount_display = f"{discount.value}% off"
                elif discount.discount_type == "fixed":
                    discount_amount = min(discount.value, cart_total)
                    discount_display = f"${discount.value} off"
                elif discount.discount_type == "free_shipping":
                    discount_amount = Decimal("0.00")  # Would affect shipping
                    discount_display = "Free shipping"
                else:
                    discount_amount = Decimal("0.00")
                    discount_display = discount.discount_type

                final_total = cart_total - discount_amount

                return JsonResponse({
                    "success": True,
                    "discount_name": discount.name,
                    "discount_type": discount.discount_type,
                    "discount_display": discount_display,
                    "discount_amount": float(discount_amount),
                    "original_total": float(cart_total),
                    "final_total": float(final_total),
                    "times_used": discount.times_used,
                    "max_uses": discount.max_uses,
                })

            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "process_refund":
            try:
                order_id = request.POST.get("order_id")
                order = Order.objects.get(id=order_id, is_test=True)

                if not order.stripe_payment_intent_id:
                    return JsonResponse({"success": False, "error": "No Stripe payment intent found for this order."})

                if order.status != OrderStatus.PAID:
                    return JsonResponse({"success": False, "error": "Only PAID orders can be refunded."})

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
                return JsonResponse({"success": False, "error": "Test order not found"})
            except stripe.StripeError as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "delete_test_order":
            try:
                order_id = request.POST.get("order_id")
                order = Order.objects.get(id=order_id, is_test=True)
                order.delete()
                return JsonResponse({
                    "success": True,
                    "message": f"Test order #{order_id} deleted.",
                })
            except Order.DoesNotExist:
                return JsonResponse({"success": False, "error": "Test order not found"})

        elif action == "create_test_product":
            try:
                import uuid
                from shop.models import Color, OrderItem, Product, ProductVariant, Size

                name = request.POST.get("name", "Test Item")
                price = Decimal(request.POST.get("price", "1.00"))
                create_order = request.POST.get("create_order") == "true"

                # Generate unique slug
                unique_id = str(uuid.uuid4())[:8]
                slug = f"test-product-{unique_id}"

                # Get or create Size M
                size_m, _ = Size.objects.get_or_create(
                    code="M",
                    defaults={"label": "Medium"}
                )

                # Get or create Color Black
                color_black, _ = Color.objects.get_or_create(
                    name="Black"
                )

                # Placeholder image (gray box with package icon)
                placeholder_svg = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='400' viewBox='0 0 400 400'%3E%3Crect fill='%23e2e8f0' width='400' height='400'/%3E%3Cpath d='M200 120l60 35v70l-60 35-60-35v-70l60-35z' fill='none' stroke='%2394a3b8' stroke-width='8'/%3E%3Cpath d='M200 155v70M140 155l60 35 60-35' fill='none' stroke='%2394a3b8' stroke-width='8'/%3E%3C/svg%3E"

                # Create the product
                product = Product.objects.create(
                    name=name,
                    slug=slug,
                    description="",
                    base_price=price,
                    is_active=True,
                    available_for_purchase=True,
                    images=[placeholder_svg],
                )

                # Create variant with stock
                variant = ProductVariant.objects.create(
                    product=product,
                    size=size_m,
                    color=color_black,
                    stock_quantity=100,
                    price=price,
                )
                variant.refresh_from_db()  # Get auto-generated SKU

                response_data = {
                    "success": True,
                    "message": f"Test product '{name}' created!",
                    "product_id": product.id,
                    "product_name": product.name,
                    "variant_id": variant.id,
                    "variant_sku": variant.sku,
                }

                # Optionally create a paid test order
                if create_order:
                    # Create Stripe PaymentIntent and auto-pay
                    intent = stripe.PaymentIntent.create(
                        amount=int(price * 100),
                        currency="usd",
                        description=f"Test Center: {name}",
                        metadata={"test_center": "true", "product_id": str(product.id)},
                        payment_method_types=["card"],
                        payment_method="pm_card_visa",
                        confirm=True,
                    )

                    # Create test order
                    order = Order.objects.create(
                        email="test@testcenter.local",
                        status=OrderStatus.PAID,
                        subtotal=price,
                        shipping=Decimal("0.00"),
                        tax=Decimal("0.00"),
                        total=price,
                        stripe_payment_intent_id=intent.id,
                        is_test=True,
                    )

                    # Create order item
                    OrderItem.objects.create(
                        order=order,
                        variant=variant,
                        sku=variant.sku,
                        quantity=1,
                        line_total=price,
                    )

                    response_data["order_id"] = order.id
                    response_data["message"] = f"Test product '{name}' and paid order #{order.id} created!"

                return JsonResponse(response_data)

            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "delete_test_product":
            try:
                from shop.models import CartItem, Product

                product_id = request.POST.get("product_id")
                product = Product.objects.get(id=product_id)

                # Check it's a test product (slug starts with test-product-)
                if not product.slug.startswith("test-product-"):
                    return JsonResponse({"success": False, "error": "Can only delete test products"})

                # Delete cart items referencing this product's variants
                variant_ids = product.variants.values_list("id", flat=True)
                deleted_cart_items = CartItem.objects.filter(variant_id__in=variant_ids).delete()[0]

                # Now delete the product (cascades to variants)
                product_name = product.name
                product.delete()

                msg = f"Deleted '{product_name}'"
                if deleted_cart_items:
                    msg += f" and {deleted_cart_items} cart item(s)"

                return JsonResponse({"success": True, "message": msg})

            except Product.DoesNotExist:
                return JsonResponse({"success": False, "error": "Product not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

    # Prepare test orders data
    test_orders_data = []
    for order in test_orders:
        test_orders_data.append({
            "id": order.id,
            "total": float(order.total),
            "status": order.status,
            "stripe_payment_intent_id": order.stripe_payment_intent_id,
            "created_at": order.created_at.isoformat(),
        })

    # Get test products (slug starts with test-product-)
    test_products = Product.objects.filter(slug__startswith="test-product-").order_by("-id")[:20]

    context = {
        "test_orders": test_orders_data,
        "test_orders_json": json.dumps(test_orders_data),
        "products": products,
        "test_products": test_products,
        "discounts": discounts,
        "stripe_publishable_key": test_publishable_key,
        "test_keys_configured": bool(test_secret_key and test_publishable_key),
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/test_center.html", context)


@staff_member_required
def test_checkout(request):
    """
    Quick test checkout - creates a $1 test product, adds to cart, redirects to checkout.
    Staff only.
    """
    from decimal import Decimal
    from django.shortcuts import redirect

    from shop.cart_utils import add_to_cart, get_or_create_cart
    from shop.models import Color, Product, ProductVariant, Size

    # Find or create the reusable test product
    test_product = Product.objects.filter(slug="test-checkout-item").first()

    # Ensure existing test product is hidden from inventory
    if test_product and test_product.is_active:
        test_product.is_active = False
        test_product.save(update_fields=["is_active"])

    if not test_product:
        # Create Size M and Color Black if needed
        size_m, _ = Size.objects.get_or_create(code="M", defaults={"label": "Medium"})
        color_black, _ = Color.objects.get_or_create(name="Black")

        # Placeholder image
        placeholder_svg = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='400' viewBox='0 0 400 400'%3E%3Crect fill='%23e2e8f0' width='400' height='400'/%3E%3Cpath d='M200 120l60 35v70l-60 35-60-35v-70l60-35z' fill='none' stroke='%2394a3b8' stroke-width='8'/%3E%3Cpath d='M200 155v70M140 155l60 35 60-35' fill='none' stroke='%2394a3b8' stroke-width='8'/%3E%3C/svg%3E"

        test_product = Product.objects.create(
            name="Test Checkout Item",
            slug="test-checkout-item",
            description="System test product - excluded from inventory",
            base_price=Decimal("1.00"),
            is_active=False,  # Hidden from shop and inventory reports
            available_for_purchase=True,
            images=[placeholder_svg],
        )

        ProductVariant.objects.create(
            product=test_product,
            size=size_m,
            color=color_black,
            stock_quantity=100,  # Minimal stock for testing
            price=Decimal("1.00"),
            images=[placeholder_svg],
        )

    # Get the variant and ensure it has placeholder image
    variant = test_product.variants.first()
    placeholder_svg = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='400' viewBox='0 0 400 400'%3E%3Crect fill='%23e2e8f0' width='400' height='400'/%3E%3Cpath d='M200 120l60 35v70l-60 35-60-35v-70l60-35z' fill='none' stroke='%2394a3b8' stroke-width='8'/%3E%3Cpath d='M200 155v70M140 155l60 35 60-35' fill='none' stroke='%2394a3b8' stroke-width='8'/%3E%3C/svg%3E"
    if not variant.images:
        variant.images = [placeholder_svg]
        variant.save()

    # Clear cart and add test item
    cart = get_or_create_cart(request)
    cart.items.all().delete()
    cart.bundle_items.all().delete()
    add_to_cart(request, variant.id, quantity=1)

    # Redirect to checkout
    return redirect("shop:checkout")
