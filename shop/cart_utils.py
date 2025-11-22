"""
Cart utility functions for managing shopping cart operations.
Handles both authenticated and anonymous users.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model

from .models import Cart, CartItem, ProductVariant

User = get_user_model()


def get_or_create_cart(request):
    """
    Get or create a cart for the current user/session.

    For authenticated users: Use user FK
    For anonymous users: Use session key
    """
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user, is_active=True)
    else:
        # Ensure session exists
        if not request.session.session_key:
            request.session.create()

        cart, created = Cart.objects.get_or_create(
            session_key=request.session.session_key, is_active=True
        )

    return cart


def add_to_cart(request, variant_id, quantity=1):
    """
    Add a product variant to the cart.

    Args:
        request: HTTP request object
        variant_id: ID of the ProductVariant to add
        quantity: Number of items to add (default: 1)

    Returns:
        tuple: (cart_item, created) - The CartItem and whether it was newly created
    """
    cart = get_or_create_cart(request)

    try:
        variant = ProductVariant.objects.get(id=variant_id, is_active=True)
    except ProductVariant.DoesNotExist:
        raise ValueError("Product variant not found or inactive")

    # Check if item already in cart
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart, variant=variant, defaults={"quantity": quantity}
    )

    if not created:
        # Item already exists, update quantity
        cart_item.quantity += quantity
        cart_item.save()

    return cart_item, created


def update_cart_item_quantity(cart_item_id, quantity, user=None, session_key=None):
    """
    Update the quantity of a cart item.

    Args:
        cart_item_id: ID of the CartItem to update
        quantity: New quantity (will be deleted if <= 0)
        user: Authenticated user (optional)
        session_key: Session key for anonymous users (optional)

    Returns:
        CartItem or None if deleted
    """
    try:
        # Build query filters
        filters = {"id": cart_item_id, "cart__is_active": True}

        if user and user.is_authenticated:
            filters["cart__user"] = user
        elif session_key:
            filters["cart__session_key"] = session_key
        else:
            raise ValueError("Must provide either user or session_key")

        cart_item = CartItem.objects.get(**filters)

        if quantity <= 0:
            cart_item.delete()
            return None
        else:
            cart_item.quantity = quantity
            cart_item.save()
            return cart_item

    except CartItem.DoesNotExist:
        raise ValueError("Cart item not found")


def remove_from_cart(cart_item_id, user=None, session_key=None):
    """
    Remove an item from the cart.

    Args:
        cart_item_id: ID of the CartItem to remove
        user: Authenticated user (optional)
        session_key: Session key for anonymous users (optional)

    Returns:
        bool: True if deleted successfully
    """
    return update_cart_item_quantity(cart_item_id, 0, user, session_key) is None


def get_cart_total(cart):
    """
    Calculate the total price of all items in the cart.

    Args:
        cart: Cart object

    Returns:
        Decimal: Total price
    """
    total = Decimal("0.00")
    for item in cart.items.all():
        total += item.variant.price * item.quantity
    return total


def get_cart_count(request):
    """
    Get the total number of items in the cart.

    Args:
        request: HTTP request object

    Returns:
        int: Total item count
    """
    try:
        cart = get_or_create_cart(request)
        return sum(item.quantity for item in cart.items.all())
    except:
        return 0


def merge_carts(user, session_key):
    """
    Merge anonymous cart into user's cart when they log in.

    Args:
        user: The authenticated User
        session_key: The session key of the anonymous cart

    Returns:
        Cart: The user's cart with merged items
    """
    # Get or create user's cart
    user_cart, _ = Cart.objects.get_or_create(user=user, is_active=True)

    # Get anonymous cart if it exists
    try:
        anonymous_cart = Cart.objects.get(session_key=session_key, is_active=True)
    except Cart.DoesNotExist:
        return user_cart

    # Merge items from anonymous cart into user cart
    for anon_item in anonymous_cart.items.all():
        user_item, created = CartItem.objects.get_or_create(
            cart=user_cart, variant=anon_item.variant, defaults={"quantity": anon_item.quantity}
        )

        if not created:
            # Item already exists in user cart, add quantities
            user_item.quantity += anon_item.quantity
            user_item.save()

    # Deactivate and clean up anonymous cart
    anonymous_cart.is_active = False
    anonymous_cart.save()
    anonymous_cart.items.all().delete()

    return user_cart


def clear_cart(cart):
    """
    Remove all items from a cart.

    Args:
        cart: Cart object
    """
    cart.items.all().delete()
