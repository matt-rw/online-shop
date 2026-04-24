"""
Views for cart and checkout functionality.
"""

import logging
from decimal import Decimal
from urllib.parse import urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from django_ratelimit.decorators import ratelimit

import stripe

from .cart_utils import (
    add_bundle_to_cart,
    add_to_cart,
    clear_cart,
    get_cart_total,
    get_or_create_cart,
    remove_bundle_from_cart,
    remove_from_cart,
    update_bundle_cart_item,
    update_cart_item_quantity,
)
from .context_processors import invalidate_cart_cache
from .models import Address, Bundle, Cart, CartItem, Order, OrderItem, ProductVariant

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY


def get_auto_free_shipping_threshold():
    """
    Get the automatic free shipping threshold from active Discount.
    Returns (threshold, discount_name) or (None, None) if no auto free shipping is active.
    """
    from django.utils import timezone
    from .models import Discount

    now = timezone.now()
    auto_discount = Discount.objects.filter(
        discount_type="auto_free_shipping",
        is_active=True,
        valid_from__lte=now,
    ).filter(
        # Valid until is either null (no expiration) or in the future
        models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=now)
    ).first()

    if auto_discount and auto_discount.min_purchase_amount:
        return (auto_discount.min_purchase_amount, auto_discount.name)
    return (None, None)


def _get_safe_referer(request, default="/"):
    """
    Get a safe redirect URL from the HTTP_REFERER header.
    Only returns the referer if it's from the same host, otherwise returns default.
    Prevents open redirect attacks via manipulated Referer headers.
    """
    referer = request.META.get("HTTP_REFERER")
    if not referer:
        return default

    try:
        parsed = urlparse(referer)
        # Only allow same-host redirects
        if parsed.netloc and parsed.netloc != request.get_host():
            return default
        # Return just the path (and query string) to avoid any scheme manipulation
        safe_url = parsed.path
        if parsed.query:
            safe_url += f"?{parsed.query}"
        return safe_url or default
    except Exception:
        return default


import json


@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@require_POST
def create_express_checkout_intent(request):
    """
    Create a PaymentIntent for Express Checkout (Apple Pay / Google Pay).
    Used on product pages for one-click purchase.
    """
    try:
        data = json.loads(request.body)
        variant_id = data.get("variant_id")
        quantity = int(data.get("quantity", 1))

        if not variant_id:
            return JsonResponse({"error": "Variant ID required"}, status=400)

        # Get the variant
        variant = get_object_or_404(ProductVariant, id=variant_id, is_active=True)

        if not variant.product.available_for_purchase:
            return JsonResponse({"error": "Product not available"}, status=400)

        if variant.stock_quantity < quantity:
            return JsonResponse({"error": "Insufficient stock"}, status=400)

        # Calculate amounts
        subtotal = variant.price * quantity
        # Check for auto free shipping threshold
        threshold, _ = get_auto_free_shipping_threshold()
        if threshold and subtotal >= threshold:
            shipping = Decimal("0.00")
        else:
            shipping = Decimal("7.99")  # Default shipping for express checkout
        total = subtotal + shipping

        # Create PaymentIntent
        intent = stripe.PaymentIntent.create(
            amount=int(total * 100),  # Convert to cents
            currency="usd",
            automatic_payment_methods={"enabled": True},
            metadata={
                "variant_id": str(variant_id),
                "quantity": str(quantity),
                "product_name": variant.product.name,
                "size": str(variant.size) if variant.size else "",
                "color": str(variant.color) if variant.color else "",
                "subtotal": str(subtotal),
                "shipping": str(shipping),
                "express_checkout": "true",
            },
        )

        return JsonResponse({
            "clientSecret": intent.client_secret,
            "paymentIntentId": intent.id,
            "subtotal": float(subtotal),
            "shipping": float(shipping),
            "total": float(total),
        })

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        logger.error(f"Express checkout error: {e}")
        return JsonResponse({"error": str(e)}, status=500)


@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@require_POST
def complete_express_checkout(request):
    """
    Complete an Express Checkout order after payment succeeds.
    Creates the order record.
    """
    try:
        data = json.loads(request.body)
        payment_intent_id = data.get("paymentIntentId")
        shipping_address = data.get("shippingAddress", {})

        if not payment_intent_id:
            return JsonResponse({"error": "Payment intent ID required"}, status=400)

        # Retrieve PaymentIntent from Stripe
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)

        if intent.status != "succeeded":
            return JsonResponse({"error": "Payment not completed"}, status=400)

        # Check if order already exists (idempotency)
        existing = Order.objects.filter(stripe_payment_intent_id=payment_intent_id).first()
        if existing:
            return JsonResponse({
                "success": True,
                "orderId": existing.id,
                "message": "Order already exists",
            })

        metadata = intent.metadata
        variant_id = metadata.get("variant_id")
        quantity = int(metadata.get("quantity", 1))
        subtotal = Decimal(metadata.get("subtotal", "0"))
        shipping = Decimal(metadata.get("shipping", "0"))

        # Get variant
        variant = ProductVariant.objects.select_related("product").get(id=variant_id)

        # Get user if authenticated
        user = request.user if request.user.is_authenticated else None

        # Get customer email from Stripe or shipping address
        customer_email = ""
        if intent.receipt_email:
            customer_email = intent.receipt_email
        elif shipping_address.get("email"):
            customer_email = shipping_address["email"]
        elif user:
            customer_email = user.email

        # Create order
        order = Order.objects.create(
            user=user,
            email=customer_email,
            status="PAID",
            subtotal=subtotal,
            shipping=shipping,
            tax=Decimal("0.00"),  # Tax handled separately if needed
            total=subtotal + shipping,
            stripe_payment_intent_id=payment_intent_id,
        )

        # Create order item
        order_item = OrderItem.objects.create(
            order=order,
            variant=variant,
            sku=str(variant.id),
            quantity=quantity,
            line_total=variant.price * quantity,
        )
        order_item.allocate_from_shipments()

        # Deduct stock
        variant.stock_quantity -= quantity
        variant.save()

        logger.info(f"Express checkout order {order.id} created for {variant.product.name}")

        return JsonResponse({
            "success": True,
            "orderId": order.id,
            "redirectUrl": f"/shop/checkout/success/?order_id={order.id}",
        })

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except ProductVariant.DoesNotExist:
        return JsonResponse({"error": "Product not found"}, status=400)
    except Exception as e:
        logger.error(f"Express checkout completion error: {e}")
        return JsonResponse({"error": str(e)}, status=500)


@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@require_POST
def add_to_cart_view(request):
    """
    Add a product variant to the cart.
    Expects POST data: variant_id OR product_id, quantity (optional, defaults to 1)
    Rate limited: 30 requests per minute per IP.
    """
    variant_id = request.POST.get("variant_id")
    product_id = request.POST.get("product_id")
    quantity = int(request.POST.get("quantity", 1))

    # If no variant_id but we have product_id, find or create a default variant
    if not variant_id and product_id:
        from .models import Product
        try:
            product = Product.objects.get(id=product_id, is_active=True)
            # Try to get the first active variant
            variant = product.variants.filter(is_active=True).first()
            if variant:
                variant_id = variant.id
            else:
                # Create a default variant for this product
                variant = ProductVariant.objects.create(
                    product=product,
                    price=product.base_price,
                    stock_quantity=100,
                    is_active=True,
                )
                variant_id = variant.id
                logger.info(f"Created default variant {variant_id} for product {product_id}")
        except Product.DoesNotExist:
            messages.error(request, "Product not found.")
            return redirect(_get_safe_referer(request))

    if not variant_id:
        messages.error(request, "Please select a product.")
        return redirect(_get_safe_referer(request))

    try:
        cart_item, created = add_to_cart(request, variant_id, quantity)

        # Invalidate cart cache
        invalidate_cart_cache(request)

        logger.info(f"Added variant {variant_id} to cart (qty: {quantity})")

        # Return JSON for AJAX requests
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            cart = get_or_create_cart(request)
            return JsonResponse(
                {
                    "success": True,
                    "message": "Item added to cart",
                    "cart_count": sum(item.quantity for item in cart.items.all()),
                    "cart_total": str(get_cart_total(cart)),
                }
            )

        return redirect("shop:cart")

    except ValueError as e:
        messages.error(request, str(e))
        logger.error(f"Error adding to cart: {e}")
        return redirect(_get_safe_referer(request))


def cart_view(request):
    """
    Display the shopping cart.
    """
    cart = get_or_create_cart(request)
    cart_items = cart.items.select_related(
        "variant__product", "variant__color", "variant__size"
    ).all()

    # Build cart items with properly prefixed image URLs
    cart_items_with_images = []
    for item in cart_items:
        image = None
        # Try variant images first
        if item.variant.images and item.variant.images[0]:
            img = item.variant.images[0]
            if img and not img.startswith(("/", "http", "data:")):
                image = f"/static/{img}"
            elif img:
                image = img
        # Fallback to product images
        if not image and item.variant.product.images:
            for img in item.variant.product.images:
                if img:
                    if not img.startswith(("/", "http", "data:")):
                        image = f"/static/{img}"
                    else:
                        image = img
                    break
        cart_items_with_images.append({
            "item": item,
            "image": image,
        })

    # Build bundle cart items
    bundle_items = cart.bundle_items.select_related("bundle", "size").prefetch_related(
        "bundle__items__product"
    ).all()

    bundle_items_with_images = []
    for item in bundle_items:
        image = None
        # Try bundle images first
        if item.bundle.images:
            for img in item.bundle.images:
                if img:
                    if not img.startswith(("/", "http", "data:")):
                        image = f"/static/{img}"
                    else:
                        image = img
                    break
        # Fallback to first component product image
        if not image:
            for bi in item.bundle.items.all():
                if bi.product.images:
                    for img in bi.product.images:
                        if img:
                            if not img.startswith(("/", "http", "data:")):
                                image = f"/static/{img}"
                            else:
                                image = img
                            break
                    if image:
                        break
        # Get component product names
        components = [bi.product.name for bi in item.bundle.items.all()]
        bundle_items_with_images.append({
            "item": item,  # Keep for cart template compatibility
            "bundle": item.bundle,
            "size": item.size,
            "quantity": item.quantity,
            "image": image,
            "components": components,  # Keep as list for cart template
            "component_names": ", ".join(components),  # Pre-joined for checkout
        })

    # Calculate totals
    subtotal = get_cart_total(cart)
    # Check for auto free shipping threshold
    threshold, _ = get_auto_free_shipping_threshold()
    free_shipping = threshold and subtotal >= threshold

    context = {
        "cart": cart,
        "cart_items": cart_items_with_images,
        "bundle_items": bundle_items_with_images,
        "subtotal": subtotal,
        "free_shipping": free_shipping,
        "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
    }

    return render(request, "shop/cart.html", context)


@ratelimit(key="ip", rate="60/m", method="POST", block=True)
@require_POST
def update_cart_item_view(request, item_id):
    """
    Update the quantity of a cart item.
    Expects POST data: quantity
    """
    quantity = int(request.POST.get("quantity", 0))

    try:
        user = request.user if request.user.is_authenticated else None
        session_key = request.session.session_key if not user else None

        cart_item = update_cart_item_quantity(item_id, quantity, user, session_key)

        # Invalidate cart cache
        invalidate_cart_cache(request)

        # Return JSON for AJAX requests
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            cart = get_or_create_cart(request)
            return JsonResponse(
                {
                    "success": True,
                    "cart_count": sum(item.quantity for item in cart.items.all()),
                    "cart_total": str(get_cart_total(cart)),
                    "item_total": (
                        str(cart_item.variant.price * cart_item.quantity) if cart_item else "0.00"
                    ),
                }
            )

        return redirect("shop:cart")

    except ValueError as e:
        messages.error(request, str(e))
        logger.error(f"Error updating cart item {item_id}: {e}")

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "error": str(e)}, status=400)

        return redirect("shop:cart")


@ratelimit(key="ip", rate="60/m", method="POST", block=True)
@require_POST
def remove_from_cart_view(request, item_id):
    """
    Remove an item from the cart.
    """
    try:
        user = request.user if request.user.is_authenticated else None
        session_key = request.session.session_key if not user else None

        remove_from_cart(item_id, user, session_key)

        # Invalidate cart cache
        invalidate_cart_cache(request)

        # Return JSON for AJAX requests
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            cart = get_or_create_cart(request)
            return JsonResponse(
                {
                    "success": True,
                    "cart_count": sum(item.quantity for item in cart.items.all()) + sum(item.quantity for item in cart.bundle_items.all()),
                    "cart_total": str(get_cart_total(cart)),
                }
            )

        return redirect("shop:cart")

    except ValueError as e:
        messages.error(request, str(e))
        logger.error(f"Error removing cart item {item_id}: {e}")

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "error": str(e)}, status=400)

        return redirect("shop:cart")


# BUNDLE CART VIEWS #


@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@require_POST
def add_bundle_to_cart_view(request):
    """
    Add a bundle to the cart with a selected size.
    Expects POST data: bundle_id, size_id, quantity (optional, defaults to 1)
    """
    bundle_id = request.POST.get("bundle_id")
    size_id = request.POST.get("size_id")
    quantity = int(request.POST.get("quantity", 1))

    if not bundle_id or not size_id:
        messages.error(request, "Please select a size.")
        return redirect(_get_safe_referer(request))

    try:
        cart_item, created = add_bundle_to_cart(request, bundle_id, size_id, quantity)

        # Invalidate cart cache
        invalidate_cart_cache(request)

        logger.info(f"Added bundle {bundle_id} size {size_id} to cart (qty: {quantity})")

        # Return JSON for AJAX requests
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            cart = get_or_create_cart(request)
            return JsonResponse(
                {
                    "success": True,
                    "message": "Bundle added to cart",
                    "cart_count": sum(item.quantity for item in cart.items.all()) + sum(item.quantity for item in cart.bundle_items.all()),
                    "cart_total": str(get_cart_total(cart)),
                }
            )

        return redirect("shop:cart")

    except ValueError as e:
        messages.error(request, str(e))
        logger.error(f"Error adding bundle to cart: {e}")

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "error": str(e)}, status=400)

        return redirect(_get_safe_referer(request))


@ratelimit(key="ip", rate="60/m", method="POST", block=True)
@require_POST
def update_bundle_item_view(request, item_id):
    """
    Update the quantity of a bundle cart item.
    Expects POST data: quantity
    """
    quantity = int(request.POST.get("quantity", 0))

    try:
        user = request.user if request.user.is_authenticated else None
        session_key = request.session.session_key if not user else None

        cart_item = update_bundle_cart_item(item_id, quantity, user, session_key)

        # Invalidate cart cache
        invalidate_cart_cache(request)

        # Return JSON for AJAX requests
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            cart = get_or_create_cart(request)
            return JsonResponse(
                {
                    "success": True,
                    "cart_count": sum(item.quantity for item in cart.items.all()) + sum(item.quantity for item in cart.bundle_items.all()),
                    "cart_total": str(get_cart_total(cart)),
                    "item_total": (
                        str(cart_item.bundle.effective_price * cart_item.quantity) if cart_item else "0.00"
                    ),
                }
            )

        return redirect("shop:cart")

    except ValueError as e:
        messages.error(request, str(e))
        logger.error(f"Error updating bundle cart item {item_id}: {e}")

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "error": str(e)}, status=400)

        return redirect("shop:cart")


@ratelimit(key="ip", rate="60/m", method="POST", block=True)
@require_POST
def remove_bundle_from_cart_view(request, item_id):
    """
    Remove a bundle from the cart.
    """
    try:
        user = request.user if request.user.is_authenticated else None
        session_key = request.session.session_key if not user else None

        remove_bundle_from_cart(item_id, user, session_key)

        # Invalidate cart cache
        invalidate_cart_cache(request)

        # Return JSON for AJAX requests
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            cart = get_or_create_cart(request)
            return JsonResponse(
                {
                    "success": True,
                    "cart_count": sum(item.quantity for item in cart.items.all()) + sum(item.quantity for item in cart.bundle_items.all()),
                    "cart_total": str(get_cart_total(cart)),
                }
            )

        return redirect("shop:cart")

    except ValueError as e:
        messages.error(request, str(e))
        logger.error(f"Error removing bundle cart item {item_id}: {e}")

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "error": str(e)}, status=400)

        return redirect("shop:cart")


def checkout_view(request):
    """
    Checkout page where users enter shipping/billing information.
    """
    cart = get_or_create_cart(request)
    cart_items = cart.items.select_related(
        "variant__product", "variant__color", "variant__size"
    ).all()

    # Also get bundle items
    bundle_items = cart.bundle_items.select_related("bundle", "size").prefetch_related(
        "bundle__items__product"
    ).all()

    # Check if cart is empty (no regular items AND no bundles)
    if not cart_items.exists() and not bundle_items.exists():
        messages.warning(request, "Your cart is empty.")
        return redirect("shop:cart")

    # Build cart items with properly prefixed image URLs
    cart_items_with_images = []
    for item in cart_items:
        image = None
        # Try variant images first
        if item.variant.images and item.variant.images[0]:
            img = item.variant.images[0]
            if img and not img.startswith(("/", "http", "data:")):
                image = f"/static/{img}"
            elif img:
                image = img
        # Fallback to product images
        if not image and item.variant.product.images:
            for img in item.variant.product.images:
                if img:
                    if not img.startswith(("/", "http", "data:")):
                        image = f"/static/{img}"
                    else:
                        image = img
                    break
        cart_items_with_images.append({
            "item": item,
            "variant": item.variant,
            "quantity": item.quantity,
            "image": image,
        })

    # Build bundle cart items with images
    bundle_items_with_images = []
    for item in bundle_items:
        image = None
        # Try bundle images first
        if item.bundle.images:
            for img in item.bundle.images:
                if img:
                    if not img.startswith(("/", "http", "data:")):
                        image = f"/static/{img}"
                    else:
                        image = img
                    break
        # Fallback to first component product image
        if not image:
            for bi in item.bundle.items.all():
                if bi.product.images:
                    for img in bi.product.images:
                        if img:
                            if not img.startswith(("/", "http", "data:")):
                                image = f"/static/{img}"
                            else:
                                image = img
                            break
                    if image:
                        break
        # Get component product names
        components = [bi.product.name for bi in item.bundle.items.all()]
        bundle_items_with_images.append({
            "item": item,  # Keep for cart template compatibility
            "bundle": item.bundle,
            "size": item.size,
            "quantity": item.quantity,
            "image": image,
            "components": components,  # Keep as list for cart template
            "component_names": ", ".join(components),  # Pre-joined for checkout
        })

    # Calculate totals
    subtotal = get_cart_total(cart)
    # Check for auto free shipping threshold
    threshold, _ = get_auto_free_shipping_threshold()
    free_shipping = threshold and subtotal >= threshold

    # Get saved addresses and user info for logged-in users
    saved_addresses = []
    user_full_name = ""
    user_email = ""
    if request.user.is_authenticated:
        saved_addresses = request.user.saved_addresses.all()
        user_full_name = request.user.get_full_name()
        user_email = request.user.email
        # Fallback to allauth email if not on user model
        if not user_email:
            try:
                from allauth.account.models import EmailAddress
                email_obj = EmailAddress.objects.filter(user=request.user, primary=True).first()
                if email_obj:
                    user_email = email_obj.email
            except Exception:
                pass

    context = {
        "cart": cart,
        "cart_items": cart_items_with_images,
        "bundle_items": bundle_items_with_images,
        "subtotal": subtotal,
        "free_shipping": free_shipping,
        "saved_addresses": saved_addresses,
        "user_full_name": user_full_name,
        "user_email": user_email,
        "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
    }

    return render(request, "shop/checkout.html", context)


@ratelimit(key="ip", rate="20/m", method="POST", block=True)
@require_POST
def get_shipping_rates_view(request):
    """
    AJAX endpoint to get real-time shipping rates based on destination address.
    Returns available shipping options from EasyPost.
    """
    import json

    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
    except json.JSONDecodeError:
        data = request.POST

    postal_code = data.get("postal_code", "").strip()
    city = data.get("city", "").strip()
    state = data.get("state", "").strip()
    country = data.get("country", "US").strip()

    if not postal_code:
        return JsonResponse({"success": False, "error": "Postal code is required"}, status=400)

    cart = get_or_create_cart(request)
    cart_items = cart.items.select_related("variant__product").all()
    bundle_items = cart.bundle_items.all()

    if not cart_items.exists() and not bundle_items.exists():
        return JsonResponse({"success": False, "error": "Cart is empty"}, status=400)

    # Check if this is a test order
    is_test_order = (
        cart_items.count() == 1
        and not bundle_items.exists()
        and cart_items.first().variant.product.slug == "test-checkout-item"
    )

    # Calculate cart subtotal for free shipping threshold
    subtotal = get_cart_total(cart)

    # Check for auto free shipping threshold
    threshold, promo_name = get_auto_free_shipping_threshold()

    # Free shipping for test orders or orders meeting threshold
    if is_test_order or (threshold and subtotal >= threshold):
        description = "Free shipping" if is_test_order else f"Free standard shipping on orders ${threshold:.0f}+"
        return JsonResponse({
            "success": True,
            "rates": [{
                "id": "free_shipping",
                "carrier": "Standard",
                "service": "Free Shipping",
                "rate": 0.00,
                "delivery_days": "5-7",
                "description": description
            }],
            "free_shipping": True
        })

    # Try to get real rates from EasyPost
    try:
        import easypost
        from shop.models import SiteSettings

        easypost_key = getattr(settings, "EASYPOST_API_KEY", None)

        if easypost_key:
            client = easypost.EasyPostClient(easypost_key)

            # Get site settings for warehouse address and default weight
            site_settings = SiteSettings.load()
            default_weight = float(site_settings.default_product_weight_oz or 8)

            # Calculate parcel based on cart items using actual product weights
            total_weight = 0
            item_count = 0
            for item in cart_items.select_related('variant__product'):
                product = item.variant.product
                # Use product weight if set, otherwise use site default
                item_weight = float(product.weight_oz) if product.weight_oz else default_weight
                total_weight += item_weight * item.quantity
                item_count += item.quantity

            # Minimum weight of 4oz
            total_weight = max(total_weight, 4)

            # Estimate dimensions based on item count
            if item_count <= 2:
                length, width, height = 10, 8, 2
            elif item_count <= 5:
                length, width, height = 12, 10, 4
            else:
                length, width, height = 14, 12, 6

            # Create shipment to get rates using warehouse from SiteSettings
            shipment = client.shipment.create(
                to_address={
                    "city": city,
                    "state": state,
                    "zip": postal_code,
                    "country": country,
                },
                from_address={
                    "name": site_settings.warehouse_name or "Blueprint Apparel",
                    "street1": site_settings.warehouse_street1 or getattr(settings, "WAREHOUSE_ADDRESS_LINE1", ""),
                    "city": site_settings.warehouse_city or getattr(settings, "WAREHOUSE_CITY", ""),
                    "state": site_settings.warehouse_state or getattr(settings, "WAREHOUSE_STATE", ""),
                    "zip": site_settings.warehouse_zip or getattr(settings, "WAREHOUSE_ZIP", ""),
                    "country": site_settings.warehouse_country or "US",
                },
                parcel={
                    "length": length,
                    "width": width,
                    "height": height,
                    "weight": total_weight,
                }
            )

            rates = []
            for rate in shipment.rates:
                # Filter to common services
                if rate.service in ["Priority", "Ground", "Express", "First", "GroundAdvantage", "PriorityMailExpress"]:
                    rates.append({
                        "id": rate.id,
                        "carrier": rate.carrier,
                        "service": rate.service,
                        "rate": float(rate.rate),
                        "delivery_days": rate.delivery_days or "3-7",
                        "description": f"{rate.carrier} {rate.service}"
                    })

            # Sort by price
            rates.sort(key=lambda x: x["rate"])

            if rates:
                return JsonResponse({"success": True, "rates": rates, "free_shipping": False})

    except ImportError:
        logger.warning("EasyPost not installed")
    except Exception as e:
        logger.error(f"EasyPost error: {e}")

    # Fallback: flat rate options
    return JsonResponse({
        "success": True,
        "rates": [
            {
                "id": "standard",
                "carrier": "USPS",
                "service": "Standard",
                "rate": 7.99,
                "delivery_days": "5-7",
                "description": "USPS Standard (5-7 business days)"
            },
            {
                "id": "priority",
                "carrier": "USPS",
                "service": "Priority",
                "rate": 12.99,
                "delivery_days": "2-3",
                "description": "USPS Priority (2-3 business days)"
            },
            {
                "id": "express",
                "carrier": "USPS",
                "service": "Express",
                "rate": 24.99,
                "delivery_days": "1-2",
                "description": "USPS Express (1-2 business days)"
            }
        ],
        "free_shipping": False,
        "fallback": True
    })


@ratelimit(key="ip", rate="10/m", method="POST", block=True)
@require_POST
def apply_promo_code(request):
    """
    AJAX endpoint to validate and apply a promo/discount code.
    Supports stacking: one free_shipping code + one percentage/fixed code.
    """
    import json
    from django.utils import timezone
    from .models import Discount

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid request"}, status=400)

    code = data.get("code", "").strip()
    subtotal = Decimal(str(data.get("subtotal", 0)))
    existing_discount_id = data.get("existing_discount_id")
    existing_discount_type = data.get("existing_discount_type")

    if not code:
        return JsonResponse({"success": False, "error": "Please enter a promo code"})

    try:
        discount = Discount.objects.get(code__iexact=code, is_active=True)
    except Discount.DoesNotExist:
        return JsonResponse({"success": False, "error": "Invalid promo code"})

    # Check validity dates
    now = timezone.now()
    if discount.valid_from and now < discount.valid_from:
        return JsonResponse({"success": False, "error": "This code is not yet active"})
    if discount.valid_until and now > discount.valid_until:
        return JsonResponse({"success": False, "error": "This code has expired"})

    # Check max uses
    if discount.max_uses and discount.times_used >= discount.max_uses:
        return JsonResponse({"success": False, "error": "This code has reached its usage limit"})

    # Check minimum purchase
    if discount.min_purchase_amount and subtotal < discount.min_purchase_amount:
        return JsonResponse({
            "success": False,
            "error": f"Minimum purchase of ${discount.min_purchase_amount:.2f} required"
        })

    # Stacking validation: check if new code is compatible with existing discount
    if existing_discount_id:
        new_type = discount.discount_type
        # Stacking rules:
        # - Allow: free_shipping + percentage
        # - Allow: free_shipping + fixed
        # - Reject: percentage + percentage
        # - Reject: fixed + fixed
        # - Reject: free_shipping + free_shipping
        if new_type == existing_discount_type:
            if new_type == "free_shipping":
                return JsonResponse({
                    "success": False,
                    "error": "You already have a free shipping code applied"
                })
            else:
                return JsonResponse({
                    "success": False,
                    "error": "You can only apply one value discount code"
                })
        # Check that we're combining free_shipping with percentage/fixed
        value_types = {"percentage", "fixed"}
        if not ((new_type == "free_shipping" and existing_discount_type in value_types) or
                (existing_discount_type == "free_shipping" and new_type in value_types)):
            return JsonResponse({
                "success": False,
                "error": "These discount codes cannot be combined"
            })

    # Calculate discount amount
    discount_amount = Decimal("0.00")
    if discount.discount_type == "percentage":
        discount_amount = (subtotal * discount.value / 100).quantize(Decimal("0.01"))
    elif discount.discount_type == "fixed":
        discount_amount = min(discount.value, subtotal)
    elif discount.discount_type == "free_shipping":
        # Handle in shipping calculation
        discount_amount = Decimal("0.00")

    # Build success message based on discount type
    if discount.discount_type == "free_shipping":
        message = f"Code '{code.upper()}' applied! Free shipping!"
    else:
        message = f"Code '{code.upper()}' applied! You saved ${discount_amount:.2f}"

    return JsonResponse({
        "success": True,
        "discount_id": discount.id,
        "discount_amount": float(discount_amount),
        "discount_type": discount.discount_type,
        "discount_code": discount.code,
        "message": message
    })


@ratelimit(key="ip", rate="10/m", method="POST", block=True)
@require_POST
def create_checkout_session(request):
    """
    Create a Stripe Checkout Session and redirect to Stripe hosted checkout.
    """
    cart = get_or_create_cart(request)
    cart_items = cart.items.select_related("variant__product").all()
    bundle_items = cart.bundle_items.select_related("bundle", "size").prefetch_related(
        "bundle__items__product"
    ).all()

    if not cart_items.exists() and not bundle_items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect("shop:cart")

    # Validate required shipping address fields
    required_shipping_fields = {
        "shipping_name": "Full Name",
        "shipping_line1": "Address Line 1",
        "shipping_city": "City",
        "shipping_region": "State/Region",
        "shipping_postal": "Postal Code",
        "shipping_country": "Country",
    }
    missing_fields = []
    for field, label in required_shipping_fields.items():
        value = request.POST.get(field, "").strip()
        if not value:
            missing_fields.append(label)

    if missing_fields:
        messages.error(request, f"Please fill in the required shipping address fields: {', '.join(missing_fields)}")
        return redirect("shop:checkout")

    try:
        # Build line items for Stripe
        line_items = []
        for item in cart_items:
            line_items.append(
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": int(item.variant.price * 100),  # Convert to cents
                        "product_data": {
                            "name": f"{item.variant.product.name} - {item.variant.size} - {item.variant.color}",
                            "description": f"SKU: {item.variant.id}",
                        },
                    },
                    "quantity": item.quantity,
                }
            )

        # Add bundle line items
        for item in bundle_items:
            components = ", ".join([bi.product.name for bi in item.bundle.items.all()])
            line_items.append(
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": int(item.bundle.effective_price * 100),  # Convert to cents
                        "product_data": {
                            "name": f"{item.bundle.name} - Size {item.size}",
                            "description": f"Bundle includes: {components}",
                        },
                    },
                    "quantity": item.quantity,
                }
            )

        # Get subtotal and selected shipping cost from form
        subtotal = get_cart_total(cart)

        # Check if this is a test order (only contains test-checkout-item)
        is_test_order = (
            cart_items.count() == 1
            and not bundle_items.exists()
            and cart_items.first().variant.product.slug == "test-checkout-item"
        )

        # Get shipping cost from form (selected by customer)
        try:
            shipping_cost = Decimal(request.POST.get("shipping_cost", "0"))
        except (ValueError, TypeError):
            shipping_cost = Decimal("0.00")

        # Check if free shipping promo code is applied
        has_free_shipping_code = bool(request.POST.get("free_shipping_discount_id", ""))

        # Check for auto free shipping threshold
        threshold, _ = get_auto_free_shipping_threshold()
        threshold_met = threshold and subtotal >= threshold

        # Track whether free shipping code is actually used (for incrementing times_used)
        free_shipping_code_used = False

        # Test orders are exempt from shipping
        if is_test_order:
            shipping_cost = Decimal("0.00")
        # Orders meeting threshold get free shipping (priority over promo code)
        elif threshold_met:
            shipping_cost = Decimal("0.00")
            # Don't mark code as used - threshold covers it
        # If free shipping code is applied and threshold NOT met, use the code
        elif has_free_shipping_code:
            shipping_cost = Decimal("0.00")
            free_shipping_code_used = True
        # Require shipping selection for orders under threshold
        elif shipping_cost <= 0:
            messages.error(request, "Please select a shipping method.")
            return redirect("shop:checkout")

        # Get customer email from form (fallback to user account email)
        customer_email = request.POST.get("email", "").strip()
        if not customer_email and request.user.is_authenticated:
            customer_email = request.user.email

        # Validate email is provided
        if not customer_email:
            messages.error(request, "Please provide an email address.")
            return redirect("shop:checkout")

        # Get shipping method details for the line item name
        shipping_rate_id = request.POST.get("shipping_rate_id", "standard")
        shipping_label = "Shipping"
        if shipping_cost == 0:
            shipping_label = "Free Shipping"

        # Add shipping as a line item (only if not free)
        if shipping_cost > 0:
            line_items.append(
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": int(shipping_cost * 100),  # Convert to cents
                        "product_data": {
                            "name": shipping_label,
                        },
                    },
                    "quantity": 1,
                }
            )

        # Handle discount/promo codes (supports stacking: free_shipping + value discount)
        discount_id = request.POST.get("discount_id", "")
        free_shipping_discount_id = request.POST.get("free_shipping_discount_id", "")
        discount_amount = Decimal("0.00")
        discount_code = ""
        free_shipping_code = ""

        from .models import Discount

        # Process free shipping discount - only record if code is actually used (not covered by threshold)
        if free_shipping_discount_id and free_shipping_code_used:
            try:
                free_shipping_obj = Discount.objects.get(id=free_shipping_discount_id, is_active=True)
                if free_shipping_obj.discount_type == "free_shipping":
                    free_shipping_code = free_shipping_obj.code
                    # Remove any shipping line item (shipping already zeroed above)
                    line_items = [
                        item for item in line_items
                        if item["price_data"]["product_data"]["name"] not in ["Shipping", "Free Shipping"]
                    ]
                    logger.info(f"Applied free shipping discount: {free_shipping_code}")
            except Exception as e:
                logger.warning(f"Error applying free shipping discount {free_shipping_discount_id}: {e}")

        # Process value discount (percentage/fixed)
        if discount_id:
            try:
                discount_obj = Discount.objects.get(id=discount_id, is_active=True)
                discount_code = discount_obj.code
                # Calculate discount amount
                if discount_obj.discount_type == "percentage":
                    discount_amount = (subtotal * discount_obj.value / 100).quantize(Decimal("0.01"))
                elif discount_obj.discount_type == "fixed":
                    discount_amount = min(discount_obj.value, subtotal)
                elif discount_obj.discount_type == "free_shipping":
                    # If only a free_shipping code was passed via discount_id (no stacking)
                    # Only use it if threshold doesn't already cover free shipping
                    if not threshold_met:
                        free_shipping_code = discount_obj.code
                        free_shipping_code_used = True
                        shipping_cost = Decimal("0.00")
                        line_items = [
                            item for item in line_items
                            if item["price_data"]["product_data"]["name"] not in ["Shipping", "Free Shipping"]
                        ]
                        logger.info(f"Applied free shipping discount: {free_shipping_code}")
                    discount_code = ""  # Clear it - we track free_shipping separately

                # Apply value discount by proportionally reducing line item prices
                if discount_amount > 0 and subtotal > 0:
                    discount_ratio = (subtotal - discount_amount) / subtotal
                    adjusted_line_items = []
                    for item in line_items:
                        # Skip shipping line item (if already added)
                        if item["price_data"]["product_data"]["name"] in ["Shipping", "Free Shipping"]:
                            adjusted_line_items.append(item)
                            continue
                        # Adjust unit amount proportionally
                        original_amount = item["price_data"]["unit_amount"]
                        adjusted_amount = int(original_amount * float(discount_ratio))
                        # Ensure at least 1 cent
                        adjusted_amount = max(adjusted_amount, 1)
                        adjusted_item = {
                            "price_data": {
                                "currency": "usd",
                                "unit_amount": adjusted_amount,
                                "product_data": item["price_data"]["product_data"],
                            },
                            "quantity": item["quantity"],
                        }
                        adjusted_line_items.append(adjusted_item)
                    line_items = adjusted_line_items
                    logger.info(f"Applied {discount_code} discount: ${discount_amount:.2f} off (ratio: {discount_ratio:.4f})")
            except Exception as e:
                logger.warning(f"Error applying discount {discount_id}: {e}")

        # Create Stripe checkout session with automatic tax calculation
        # Note: Stripe Tax must be enabled in your Stripe Dashboard first
        # Order will be created in webhook after successful payment
        # Test orders are exempt from tax
        session_params = {
            "line_items": line_items,
            "mode": "payment",
            "automatic_tax": {"enabled": not is_test_order},
            "success_url": request.build_absolute_uri("/shop/checkout/success/")
            + "?session_id={CHECKOUT_SESSION_ID}",
            "cancel_url": request.build_absolute_uri("/shop/checkout/"),
            "customer_email": customer_email if customer_email else None,
            "metadata": {
                "cart_id": str(cart.id),
                "user_id": str(request.user.id) if request.user.is_authenticated else "",
                "customer_email": customer_email or "",
                "subtotal": str(subtotal),
                "shipping_cost": str(shipping_cost),
                "is_test_order": "true" if is_test_order else "false",
                "discount_code": discount_code,
                "discount_amount": str(discount_amount),
                "free_shipping_code": free_shipping_code,
                # Shipping address
                "shipping_name": request.POST.get("shipping_name", ""),
                "shipping_line1": request.POST.get("shipping_line1", ""),
                "shipping_line2": request.POST.get("shipping_line2", ""),
                "shipping_city": request.POST.get("shipping_city", ""),
                "shipping_region": request.POST.get("shipping_region", ""),
                "shipping_postal": request.POST.get("shipping_postal", ""),
                "shipping_country": request.POST.get("shipping_country", "US"),
            },
        }

        session = stripe.checkout.Session.create(**session_params)

        logger.info(f"Created Stripe checkout session {session.id} for cart {cart.id}")

        return redirect(session.url, code=303)

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error creating checkout session: {error_msg}")

        # Provide helpful error messages
        if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
            messages.error(request, "Payment system configuration error. Please contact support.")
        else:
            messages.error(request, f"There was an error processing your checkout: {error_msg[:100]}")
        return redirect("shop:checkout")


def checkout_success_view(request):
    """
    Display order confirmation after successful payment.
    Order is created by webhook, but we handle the case where webhook hasn't run yet.
    Supports both Stripe Checkout (session_id) and Express Checkout (order_id).
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    # Handle Express Checkout (order already created)
    order_id = request.GET.get("order_id")
    if order_id:
        try:
            order = Order.objects.get(id=order_id)
            context = {"order": order}
            return render(request, "shop/checkout_success.html", context)
        except Order.DoesNotExist:
            messages.error(request, "Order not found.")
            return redirect("home")

    session_id = request.GET.get("session_id")

    if not session_id:
        messages.error(request, "Invalid checkout session.")
        return redirect("home")

    try:
        # Retrieve the session from Stripe
        session = stripe.checkout.Session.retrieve(session_id)

        # Check payment status
        if session.payment_status != "paid":
            messages.error(request, "Payment was not completed.")
            return redirect("shop:checkout")

        # Try to find existing order (created by webhook)
        order = Order.objects.filter(stripe_checkout_id=session_id).first()

        # If webhook hasn't created the order yet, create it now
        if not order:
            metadata = session.metadata or {}
            cart_id = metadata.get("cart_id")

            if not cart_id:
                messages.error(request, "Invalid checkout session.")
                return redirect("home")

            try:
                cart = Cart.objects.get(id=cart_id)
                cart_items = cart.items.select_related("variant__product").all()
                bundle_items = cart.bundle_items.select_related(
                    "bundle", "size"
                ).prefetch_related("bundle__items__product").all()

                if cart_items.exists() or bundle_items.exists():
                    # Get user if exists
                    user = None
                    user_id = metadata.get("user_id")
                    if user_id:
                        try:
                            user = User.objects.get(id=user_id)
                        except User.DoesNotExist:
                            pass

                    # Get customer email
                    customer_email = metadata.get("customer_email") or ""
                    if not customer_email and session.customer_details:
                        customer_email = session.customer_details.email or ""

                    # Parse amounts
                    subtotal = Decimal(metadata.get("subtotal", "0"))
                    shipping_cost = Decimal(metadata.get("shipping_cost", "0"))

                    # Get tax from Stripe (amount is in cents)
                    tax_amount = Decimal("0.00")
                    if session.total_details and session.total_details.amount_tax:
                        tax_amount = Decimal(session.total_details.amount_tax) / 100

                    # Calculate total (use Stripe's amount_total for accuracy)
                    total = subtotal + shipping_cost + tax_amount
                    if session.amount_total:
                        total = Decimal(session.amount_total) / 100

                    # Extract shipping address from Stripe session or metadata
                    shipping_address = None
                    stripe_shipping = getattr(session, 'shipping_details', None) or getattr(session, 'shipping', None)
                    if stripe_shipping and stripe_shipping.address:
                        # Stripe collected the address directly
                        addr = stripe_shipping.address
                        shipping_address = Address.objects.create(
                            full_name=stripe_shipping.name or "",
                            line1=addr.line1 or "",
                            line2=addr.line2 or "",
                            city=addr.city or "",
                            region=addr.state or "",
                            postal_code=addr.postal_code or "",
                            country=addr.country or "US",
                            email=customer_email,
                        )
                        logger.info(f"Created shipping address from Stripe: {shipping_address.city}, {shipping_address.region}")
                    elif metadata.get("shipping_line1") and metadata.get("shipping_city"):
                        # Address was passed in metadata from checkout form
                        shipping_address = Address.objects.create(
                            full_name=metadata.get("shipping_name", ""),
                            line1=metadata.get("shipping_line1", ""),
                            line2=metadata.get("shipping_line2", "") or "",
                            city=metadata.get("shipping_city", ""),
                            region=metadata.get("shipping_region", ""),
                            postal_code=metadata.get("shipping_postal", ""),
                            country=metadata.get("shipping_country", "US"),
                            email=customer_email,
                        )
                        logger.info(f"Created shipping address from metadata: {shipping_address.city}, {shipping_address.region}")

                    # Get discount codes from metadata
                    discount_code = metadata.get("discount_code", "")
                    discount_amount = Decimal(metadata.get("discount_amount", "0"))
                    free_shipping_code = metadata.get("free_shipping_code", "")

                    # Create order
                    order = Order.objects.create(
                        user=user,
                        email=customer_email,
                        status="PAID",
                        subtotal=subtotal,
                        discount=discount_amount,
                        discount_code=discount_code,
                        free_shipping_code=free_shipping_code,
                        shipping=shipping_cost,
                        tax=tax_amount,
                        total=total,
                        stripe_checkout_id=session_id,
                        stripe_payment_intent_id=session.payment_intent,
                        shipping_address=shipping_address,
                    )

                    # Create order items from regular cart items
                    for item in cart_items:
                        order_item = OrderItem.objects.create(
                            order=order,
                            variant=item.variant,
                            sku=str(item.variant.id),
                            quantity=item.quantity,
                            line_total=item.variant.price * item.quantity,
                        )
                        # Allocate from shipment batches (FIFO)
                        order_item.allocate_from_shipments()

                    # Create order items from bundles (expanded into individual components)
                    for bundle_cart_item in bundle_items:
                        variants = bundle_cart_item.bundle.get_variants_for_size(
                            bundle_cart_item.size
                        )
                        if variants:
                            for bundle_item, variant in variants:
                                total_qty = bundle_item.quantity * bundle_cart_item.quantity
                                # Calculate proportional line total from bundle price
                                order_item = OrderItem.objects.create(
                                    order=order,
                                    variant=variant,
                                    sku=str(variant.id),
                                    quantity=total_qty,
                                    line_total=variant.price * total_qty,
                                )
                                # Allocate from shipment batches (FIFO)
                                order_item.allocate_from_shipments()

                    # Clear cart
                    cart.items.all().delete()
                    cart.bundle_items.all().delete()
                    cart.is_active = False
                    cart.save()

                    logger.info(f"Order {order.id} created in success view (webhook fallback)")

                    # Send order confirmation email to customer
                    try:
                        from shop.utils.email_helper import send_order_confirmation
                        success, log = send_order_confirmation(order)
                        if success:
                            logger.info(f"Order confirmation email sent for {order.order_number}")
                        else:
                            logger.info(f"Order confirmation email not sent for {order.order_number}")
                    except Exception as e:
                        logger.error(f"Error sending order confirmation email: {e}")

                    # Send order notification email to admin
                    try:
                        from shop.utils.email_helper import send_order_admin_notification
                        success, log = send_order_admin_notification(order)
                        if success:
                            logger.info(f"Admin order notification sent for {order.order_number}")
                        else:
                            logger.info(f"Admin order notification not sent for {order.order_number}")
                    except Exception as e:
                        logger.error(f"Error sending admin order notification: {e}")

            except Cart.DoesNotExist:
                pass

        if not order:
            messages.error(request, "Could not find your order. Please contact support.")
            return redirect("home")

        context = {
            "order": order,
            "session": session,
        }

        return render(request, "shop/checkout_success.html", context)

    except Exception as e:
        import traceback
        logger.error(f"Error in checkout success: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        messages.error(request, "There was an error retrieving your order.")
        return redirect("home")
