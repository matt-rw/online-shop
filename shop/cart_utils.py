"""
Cart utility functions for managing shopping cart operations.
Handles both authenticated and anonymous users.
"""

import logging
from decimal import Decimal

from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)

from .models import Bundle, BundleCartItem, Cart, CartItem, ProductVariant, Size

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

    Raises:
        ValueError: If variant not found, inactive, or insufficient stock
    """
    cart = get_or_create_cart(request)

    try:
        variant = ProductVariant.objects.get(id=variant_id, is_active=True)
    except ProductVariant.DoesNotExist:
        raise ValueError("Product variant not found or inactive")

    # Check if item already in cart
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart, variant=variant, defaults={"quantity": 0}
    )

    # Calculate new total quantity
    new_quantity = cart_item.quantity + quantity

    # Check stock availability
    if new_quantity > variant.stock_quantity:
        available = variant.stock_quantity - cart_item.quantity
        if available <= 0:
            raise ValueError(f"No more stock available. Maximum quantity already in cart.")
        else:
            raise ValueError(f"Only {available} more available. {variant.stock_quantity} total in stock.")

    cart_item.quantity = new_quantity
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

    Raises:
        ValueError: If cart item not found or quantity exceeds stock
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

        cart_item = CartItem.objects.select_related('variant').get(**filters)

        if quantity <= 0:
            cart_item.delete()
            return None
        else:
            # Check stock availability
            if quantity > cart_item.variant.stock_quantity:
                raise ValueError(
                    f"Only {cart_item.variant.stock_quantity} available in stock."
                )
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
    Calculate the total price of all items in the cart (products + bundles).

    Args:
        cart: Cart object

    Returns:
        Decimal: Total price
    """
    total = Decimal("0.00")
    # Regular cart items
    for item in cart.items.select_related("variant"):
        total += item.variant.price * item.quantity
    # Bundle cart items
    for item in cart.bundle_items.select_related("bundle"):
        total += item.bundle.effective_price * item.quantity
    return total


def get_cart_count(request):
    """
    Get the total number of items in the cart (products + bundles).

    Args:
        request: HTTP request object

    Returns:
        int: Total item count
    """
    try:
        cart = get_or_create_cart(request)
        count = sum(item.quantity for item in cart.items.all())
        count += sum(item.quantity for item in cart.bundle_items.all())
        return count
    except Exception as e:
        logger.error(f"Error getting cart count: {e}")
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

    # Merge regular items from anonymous cart into user cart
    for anon_item in anonymous_cart.items.all():
        user_item, created = CartItem.objects.get_or_create(
            cart=user_cart, variant=anon_item.variant, defaults={"quantity": anon_item.quantity}
        )

        if not created:
            # Item already exists in user cart, add quantities
            user_item.quantity += anon_item.quantity
            user_item.save()

    # Merge bundle items from anonymous cart into user cart
    for anon_item in anonymous_cart.bundle_items.all():
        user_item, created = BundleCartItem.objects.get_or_create(
            cart=user_cart,
            bundle=anon_item.bundle,
            size=anon_item.size,
            defaults={"quantity": anon_item.quantity},
        )

        if not created:
            user_item.quantity += anon_item.quantity
            user_item.save()

    # Deactivate and clean up anonymous cart
    anonymous_cart.is_active = False
    anonymous_cart.save()
    anonymous_cart.items.all().delete()
    anonymous_cart.bundle_items.all().delete()

    return user_cart


def clear_cart(cart):
    """
    Remove all items from a cart.

    Args:
        cart: Cart object
    """
    cart.items.all().delete()
    cart.bundle_items.all().delete()


# BUNDLE CART FUNCTIONS #


def add_bundle_to_cart(request, bundle_id, size_id, quantity=1):
    """
    Add a bundle to the cart with a selected size.

    Args:
        request: HTTP request object
        bundle_id: ID of the Bundle to add
        size_id: ID of the Size selected
        quantity: Number of bundles to add (default: 1)

    Returns:
        tuple: (bundle_cart_item, created)

    Raises:
        ValueError: If bundle not found, inactive, or insufficient stock
    """
    cart = get_or_create_cart(request)

    try:
        bundle = Bundle.objects.prefetch_related("items__product").get(
            id=bundle_id, is_active=True, available_for_purchase=True
        )
    except Bundle.DoesNotExist:
        raise ValueError("Bundle not found or not available for purchase")

    # Check if all component products are available for purchase
    if not bundle.all_components_available:
        raise ValueError("One or more items in this bundle are not available for purchase")

    try:
        size = Size.objects.get(id=size_id)
    except Size.DoesNotExist:
        raise ValueError("Size not found")

    # Check if bundle is available in this size
    variants = bundle.get_variants_for_size(size)
    if not variants:
        raise ValueError(f"Bundle not available in size {size}")

    # Check if item already in cart
    cart_item, created = BundleCartItem.objects.get_or_create(
        cart=cart, bundle=bundle, size=size, defaults={"quantity": 0}
    )

    new_quantity = cart_item.quantity + quantity

    # Check stock availability for all components
    for bundle_item, variant in variants:
        required = bundle_item.quantity * new_quantity
        if required > variant.stock_quantity:
            available = variant.stock_quantity // bundle_item.quantity
            raise ValueError(
                f"Only {available} bundle(s) available due to {variant.product.name} stock"
            )

    cart_item.quantity = new_quantity
    cart_item.save()

    return cart_item, created


def update_bundle_cart_item(cart_item_id, quantity, user=None, session_key=None):
    """
    Update the quantity of a bundle cart item.

    Args:
        cart_item_id: ID of the BundleCartItem to update
        quantity: New quantity (will be deleted if <= 0)
        user: Authenticated user (optional)
        session_key: Session key for anonymous users (optional)

    Returns:
        BundleCartItem or None if deleted

    Raises:
        ValueError: If cart item not found or quantity exceeds stock
    """
    try:
        filters = {"id": cart_item_id, "cart__is_active": True}

        if user and user.is_authenticated:
            filters["cart__user"] = user
        elif session_key:
            filters["cart__session_key"] = session_key
        else:
            raise ValueError("Must provide either user or session_key")

        cart_item = BundleCartItem.objects.select_related("bundle", "size").get(**filters)

        if quantity <= 0:
            cart_item.delete()
            return None

        # Check stock availability
        variants = cart_item.bundle.get_variants_for_size(cart_item.size)
        if not variants:
            raise ValueError("Bundle no longer available in this size")

        for bundle_item, variant in variants:
            required = bundle_item.quantity * quantity
            if required > variant.stock_quantity:
                available = variant.stock_quantity // bundle_item.quantity
                raise ValueError(f"Only {available} bundle(s) available")

        cart_item.quantity = quantity
        cart_item.save()
        return cart_item

    except BundleCartItem.DoesNotExist:
        raise ValueError("Bundle cart item not found")


def remove_bundle_from_cart(cart_item_id, user=None, session_key=None):
    """
    Remove a bundle from the cart.

    Args:
        cart_item_id: ID of the BundleCartItem to remove
        user: Authenticated user (optional)
        session_key: Session key for anonymous users (optional)

    Returns:
        bool: True if deleted successfully
    """
    return update_bundle_cart_item(cart_item_id, 0, user, session_key) is None
