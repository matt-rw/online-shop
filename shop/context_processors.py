"""
Context processors to make data available in all templates.
"""

from .cart_utils import get_cart_count, get_cart_total, get_or_create_cart


def cart_context(request):
    """
    Add cart information to all template contexts.
    """
    try:
        cart = get_or_create_cart(request)
        cart_count = sum(item.quantity for item in cart.items.all())
        cart_total = get_cart_total(cart)
    except:
        cart_count = 0
        cart_total = 0

    return {
        "cart_count": cart_count,
        "cart_total": cart_total,
    }
