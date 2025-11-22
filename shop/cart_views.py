"""
Views for cart and checkout functionality.
"""

import logging
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

import stripe

from .cart_utils import (
    add_to_cart,
    clear_cart,
    get_cart_total,
    get_or_create_cart,
    remove_from_cart,
    update_cart_item_quantity,
)
from .models import Address, CartItem, Order, OrderItem, ProductVariant

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY


@require_POST
def add_to_cart_view(request):
    """
    Add a product variant to the cart.
    Expects POST data: variant_id, quantity (optional, defaults to 1)
    """
    variant_id = request.POST.get("variant_id")
    quantity = int(request.POST.get("quantity", 1))

    if not variant_id:
        messages.error(request, "Please select a product variant.")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    try:
        cart_item, created = add_to_cart(request, variant_id, quantity)

        if created:
            messages.success(request, f"Added {cart_item.variant} to your cart!")
        else:
            messages.success(request, f"Updated {cart_item.variant} quantity in cart.")

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
        return redirect(request.META.get("HTTP_REFERER", "/"))


def cart_view(request):
    """
    Display the shopping cart.
    """
    cart = get_or_create_cart(request)
    cart_items = cart.items.select_related(
        "variant__product", "variant__color", "variant__size"
    ).all()

    # Calculate totals
    subtotal = get_cart_total(cart)
    # TODO: Calculate shipping and tax based on user location
    shipping = Decimal("0.00")  # Free shipping for now
    tax = Decimal("0.00")  # Calculate tax at checkout
    total = subtotal + shipping + tax

    context = {
        "cart": cart,
        "cart_items": cart_items,
        "subtotal": subtotal,
        "shipping": shipping,
        "tax": tax,
        "total": total,
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

        if cart_item:
            messages.success(request, "Cart updated successfully.")
        else:
            messages.success(request, "Item removed from cart.")

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
        messages.success(request, "Item removed from cart.")

        # Return JSON for AJAX requests
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            cart = get_or_create_cart(request)
            return JsonResponse(
                {
                    "success": True,
                    "cart_count": sum(item.quantity for item in cart.items.all()),
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


def checkout_view(request):
    """
    Checkout page where users enter shipping/billing information.
    """
    cart = get_or_create_cart(request)
    cart_items = cart.items.select_related("variant__product").all()

    if not cart_items.exists():
        messages.warning(request, "Your cart is empty.")
        return redirect("shop:cart")

    # Calculate totals
    subtotal = get_cart_total(cart)
    shipping = Decimal("10.00")  # Flat rate shipping
    tax = subtotal * Decimal("0.07")  # 7% tax (should be based on location)
    total = subtotal + shipping + tax

    # Get saved addresses for logged-in users
    saved_addresses = []
    if request.user.is_authenticated:
        saved_addresses = request.user.saved_addresses.all()

    context = {
        "cart": cart,
        "cart_items": cart_items,
        "subtotal": subtotal,
        "shipping": shipping,
        "tax": tax,
        "total": total,
        "saved_addresses": saved_addresses,
        "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
    }

    return render(request, "shop/checkout.html", context)


@require_POST
def create_checkout_session(request):
    """
    Create a Stripe Checkout Session and redirect to Stripe hosted checkout.
    """
    cart = get_or_create_cart(request)
    cart_items = cart.items.select_related("variant__product").all()

    if not cart_items.exists():
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

        # Add shipping as a line item
        line_items.append(
            {
                "price_data": {
                    "currency": "usd",
                    "unit_amount": 1000,  # $10.00 flat rate
                    "product_data": {
                        "name": "Shipping",
                    },
                },
                "quantity": 1,
            }
        )

        # Create Stripe checkout session
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="payment",
            success_url=request.build_absolute_uri("/shop/checkout/success/")
            + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=request.build_absolute_uri("/shop/checkout/"),
            customer_email=request.user.email if request.user.is_authenticated else None,
            metadata={
                "cart_id": cart.id,
                "user_id": request.user.id if request.user.is_authenticated else None,
            },
        )

        # Create Order record
        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            email=request.user.email if request.user.is_authenticated else "",
            status="AWAITING_PAYMENT",
            subtotal=get_cart_total(cart),
            shipping=Decimal("10.00"),
            tax=get_cart_total(cart) * Decimal("0.07"),
            total=get_cart_total(cart)
            + Decimal("10.00")
            + (get_cart_total(cart) * Decimal("0.07")),
            stripe_checkout_id=session.id,
        )

        # Copy cart items to order items
        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                variant=item.variant,
                sku=str(item.variant.id),
                quantity=item.quantity,
                line_total=item.variant.price * item.quantity,
            )

        logger.info(f"Created Stripe checkout session {session.id} for order {order.id}")

        return redirect(session.url, code=303)

    except Exception as e:
        logger.error(f"Error creating checkout session: {e}")
        messages.error(request, "There was an error processing your checkout. Please try again.")
        return redirect("shop:checkout")


def checkout_success_view(request):
    """
    Display order confirmation after successful payment.
    """
    session_id = request.GET.get("session_id")

    if not session_id:
        messages.error(request, "Invalid checkout session.")
        return redirect("home:home")

    try:
        # Retrieve the session from Stripe
        session = stripe.checkout.Session.retrieve(session_id)

        # Find the order
        order = Order.objects.get(stripe_checkout_id=session_id)

        # Clear the cart
        cart_id = session.metadata.get("cart_id")
        if cart_id:
            try:
                cart = Cart.objects.get(id=cart_id)
                clear_cart(cart)
                cart.is_active = False
                cart.save()
            except Cart.DoesNotExist:
                pass

        context = {
            "order": order,
            "session": session,
        }

        return render(request, "shop/checkout_success.html", context)

    except Exception as e:
        logger.error(f"Error in checkout success: {e}")
        messages.error(request, "There was an error retrieving your order.")
        return redirect("home:home")
