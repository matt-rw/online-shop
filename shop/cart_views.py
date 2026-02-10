"""
Views for cart and checkout functionality.
"""

import logging
from decimal import Decimal
from urllib.parse import urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

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
from .models import Address, Bundle, Cart, CartItem, Order, OrderItem, ProductVariant

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY


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


@require_POST
def add_to_cart_view(request):
    """
    Add a product variant to the cart.
    Expects POST data: variant_id OR product_id, quantity (optional, defaults to 1)
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

        # Silently add to cart without notification

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
        if item.variant.images and item.variant.images[0]:
            img = item.variant.images[0]
            # Ensure image has proper static prefix
            if not img.startswith(("/", "http")):
                image = f"/static/{img}"
            else:
                image = img
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
        if item.bundle.images and item.bundle.images[0]:
            img = item.bundle.images[0]
            if not img.startswith(("/", "http")):
                image = f"/static/{img}"
            else:
                image = img
        # Get component product names
        components = [bi.product.name for bi in item.bundle.items.all()]
        bundle_items_with_images.append({
            "item": item,
            "image": image,
            "components": components,
        })

    # Calculate totals
    subtotal = get_cart_total(cart)
    # Shipping is calculated at checkout based on destination
    # Free shipping on orders $100+
    free_shipping = subtotal >= Decimal("100.00")

    context = {
        "cart": cart,
        "cart_items": cart_items_with_images,
        "bundle_items": bundle_items_with_images,
        "subtotal": subtotal,
        "free_shipping": free_shipping,
        "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
    }

    return render(request, "shop/cart.html", context)


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

        # Silently update cart without notification

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


@require_POST
def remove_from_cart_view(request, item_id):
    """
    Remove an item from the cart.
    """
    try:
        user = request.user if request.user.is_authenticated else None
        session_key = request.session.session_key if not user else None

        remove_from_cart(item_id, user, session_key)
        # Silently remove from cart without notification

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


@require_POST
def remove_bundle_from_cart_view(request, item_id):
    """
    Remove a bundle from the cart.
    """
    try:
        user = request.user if request.user.is_authenticated else None
        session_key = request.session.session_key if not user else None

        remove_bundle_from_cart(item_id, user, session_key)

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

    if not cart_items.exists():
        messages.warning(request, "Your cart is empty.")
        return redirect("shop:cart")

    # Build cart items with properly prefixed image URLs
    cart_items_with_images = []
    for item in cart_items:
        image = None
        if item.variant.images and item.variant.images[0]:
            img = item.variant.images[0]
            # Ensure image has proper static prefix
            if not img.startswith(("/", "http")):
                image = f"/static/{img}"
            else:
                image = img
        cart_items_with_images.append({
            "item": item,
            "variant": item.variant,
            "quantity": item.quantity,
            "image": image,
        })

    # Calculate totals
    subtotal = get_cart_total(cart)
    # Free shipping on orders $100+
    free_shipping = subtotal >= Decimal("100.00")

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
        "subtotal": subtotal,
        "free_shipping": free_shipping,
        "saved_addresses": saved_addresses,
        "user_full_name": user_full_name,
        "user_email": user_email,
        "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
    }

    return render(request, "shop/checkout.html", context)


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

    if not cart_items.exists():
        return JsonResponse({"success": False, "error": "Cart is empty"}, status=400)

    # Calculate cart subtotal for free shipping threshold
    subtotal = get_cart_total(cart)

    # Free shipping on orders $100+
    if subtotal >= Decimal("100.00"):
        return JsonResponse({
            "success": True,
            "rates": [{
                "id": "free_shipping",
                "carrier": "Standard",
                "service": "Free Shipping",
                "rate": 0.00,
                "delivery_days": "5-7",
                "description": "Free standard shipping on orders $100+"
            }],
            "free_shipping": True
        })

    # Try to get real rates from EasyPost
    try:
        import easypost
        easypost_key = getattr(settings, "EASYPOST_API_KEY", None)

        if easypost_key:
            client = easypost.EasyPostClient(easypost_key)

            # Calculate parcel based on cart items
            total_weight = 0
            for item in cart_items:
                # Estimate weight: 8oz per item (typical for apparel)
                total_weight += item.quantity * 8

            # Create shipment to get rates
            shipment = client.shipment.create(
                to_address={
                    "city": city,
                    "state": state,
                    "zip": postal_code,
                    "country": country,
                },
                from_address={
                    "name": getattr(settings, "WAREHOUSE_NAME", "Blueprint Apparel"),
                    "street1": getattr(settings, "WAREHOUSE_ADDRESS_LINE1", "123 Fashion Ave"),
                    "city": getattr(settings, "WAREHOUSE_CITY", "New York"),
                    "state": getattr(settings, "WAREHOUSE_STATE", "NY"),
                    "zip": getattr(settings, "WAREHOUSE_ZIP", "10001"),
                    "country": "US",
                },
                parcel={
                    "length": 12,
                    "width": 10,
                    "height": 4,
                    "weight": max(total_weight, 8),  # Minimum 8oz
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

        # Get shipping cost from form (selected by customer)
        try:
            shipping_cost = Decimal(request.POST.get("shipping_cost", "0"))
        except (ValueError, TypeError):
            shipping_cost = Decimal("0.00")

        # Validate shipping - free only if subtotal >= $100
        if subtotal < Decimal("100.00") and shipping_cost <= 0:
            # Fallback to standard rate if no shipping selected
            shipping_cost = Decimal("7.99")

        # Get customer email from form (fallback to user account email)
        customer_email = request.POST.get("email", "").strip()
        if not customer_email and request.user.is_authenticated:
            customer_email = request.user.email

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

        # Create Stripe checkout session
        # Note: To enable automatic tax calculation, set up Stripe Tax in your dashboard
        # and uncomment automatic_tax below
        # Order will be created in webhook after successful payment
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="payment",
            # automatic_tax={"enabled": True},  # Enable after setting up Stripe Tax
            success_url=request.build_absolute_uri("/shop/checkout/success/")
            + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=request.build_absolute_uri("/shop/checkout/"),
            customer_email=customer_email if customer_email else None,
            metadata={
                "cart_id": str(cart.id),
                "user_id": str(request.user.id) if request.user.is_authenticated else "",
                "customer_email": customer_email or "",
                "subtotal": str(subtotal),
                "shipping_cost": str(shipping_cost),
                # Shipping address
                "shipping_name": request.POST.get("shipping_name", ""),
                "shipping_line1": request.POST.get("shipping_line1", ""),
                "shipping_line2": request.POST.get("shipping_line2", ""),
                "shipping_city": request.POST.get("shipping_city", ""),
                "shipping_region": request.POST.get("shipping_region", ""),
                "shipping_postal": request.POST.get("shipping_postal", ""),
                "shipping_country": request.POST.get("shipping_country", "US"),
            },
        )

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
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    session_id = request.GET.get("session_id")

    if not session_id:
        messages.error(request, "Invalid checkout session.")
        return redirect("home:home")

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
                return redirect("home:home")

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
                        customer_email = session.customer_details.get("email", "")

                    # Parse amounts
                    subtotal = Decimal(metadata.get("subtotal", "0"))
                    shipping_cost = Decimal(metadata.get("shipping_cost", "0"))

                    # Create order
                    order = Order.objects.create(
                        user=user,
                        email=customer_email,
                        status="PAID",
                        subtotal=subtotal,
                        shipping=shipping_cost,
                        tax=Decimal("0.00"),
                        total=subtotal + shipping_cost,
                        stripe_checkout_id=session_id,
                        stripe_payment_intent_id=session.payment_intent,
                    )

                    # Create order items from regular cart items
                    for item in cart_items:
                        OrderItem.objects.create(
                            order=order,
                            variant=item.variant,
                            sku=str(item.variant.id),
                            quantity=item.quantity,
                            line_total=item.variant.price * item.quantity,
                        )

                    # Create order items from bundles (expanded into individual components)
                    for bundle_cart_item in bundle_items:
                        variants = bundle_cart_item.bundle.get_variants_for_size(
                            bundle_cart_item.size
                        )
                        if variants:
                            for bundle_item, variant in variants:
                                total_qty = bundle_item.quantity * bundle_cart_item.quantity
                                # Calculate proportional line total from bundle price
                                OrderItem.objects.create(
                                    order=order,
                                    variant=variant,
                                    sku=str(variant.id),
                                    quantity=total_qty,
                                    line_total=variant.price * total_qty,
                                )

                    # Clear cart
                    cart.items.all().delete()
                    cart.bundle_items.all().delete()
                    cart.is_active = False
                    cart.save()

                    logger.info(f"Order {order.id} created in success view (webhook fallback)")

            except Cart.DoesNotExist:
                pass

        if not order:
            messages.error(request, "Could not find your order. Please contact support.")
            return redirect("home:home")

        context = {
            "order": order,
            "session": session,
        }

        return render(request, "shop/checkout_success.html", context)

    except Exception as e:
        logger.error(f"Error in checkout success: {e}")
        messages.error(request, "There was an error retrieving your order.")
        return redirect("home:home")
