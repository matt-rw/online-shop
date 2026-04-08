"""
Context processors to make data available in all templates.
"""

from django.core.cache import cache
from django.db import models

from .cart_utils import get_cart_count, get_cart_total, get_or_create_cart


# Cache timeout for site settings (5 minutes)
SITE_SETTINGS_CACHE_TIMEOUT = 300


def cart_context(request):
    """
    Add cart information to all template contexts.
    Uses session-cached cart count to minimize database queries.
    """
    try:
        # For non-authenticated users with session cart, use session-cached count
        cart_session_key = request.session.session_key
        cache_key = f"cart_count_{cart_session_key}" if cart_session_key else None

        # Try to get cached count first
        cached_count = cache.get(cache_key) if cache_key else None

        if cached_count is not None:
            cart_count = cached_count
            # Still need to calculate total for display, but only if needed
            cart = get_or_create_cart(request)
            cart_total = get_cart_total(cart)
        else:
            cart = get_or_create_cart(request)
            cart_count = sum(item.quantity for item in cart.items.all())
            cart_total = get_cart_total(cart)

            # Cache the count for 60 seconds (will be invalidated on cart changes)
            if cache_key:
                cache.set(cache_key, cart_count, 60)
    except Exception:
        cart_count = 0
        cart_total = 0

    return {
        "cart_count": cart_count,
        "cart_total": cart_total,
    }


def site_settings_context(request):
    """
    Add site settings to all template contexts.
    Cached to avoid database query on every request.
    """
    cache_key = "site_settings_context"

    # Try cache first
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data

    from .models import SiteSettings

    try:
        site_settings = SiteSettings.load()

        # Get auto free shipping threshold from Discount model
        from django.utils import timezone
        from .models import Discount
        now = timezone.now()
        auto_discount = Discount.objects.filter(
            discount_type="auto_free_shipping",
            is_active=True,
            valid_from__lte=now,
        ).filter(
            models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=now)
        ).first()
        free_shipping_threshold = float(auto_discount.min_purchase_amount) if auto_discount and auto_discount.min_purchase_amount else 0

        data = {
            "site_settings": site_settings,
            "gallery_images": site_settings.gallery_images or [],
            "hero_slides": site_settings.hero_slides or [],
            "free_shipping_threshold": free_shipping_threshold,
        }
    except Exception:
        data = {
            "site_settings": None,
            "gallery_images": [],
            "hero_slides": [],
            "free_shipping_threshold": 0,
        }

    # Cache for 5 minutes
    cache.set(cache_key, data, SITE_SETTINGS_CACHE_TIMEOUT)
    return data


def invalidate_site_settings_cache():
    """
    Call this function when site settings are updated to clear the cache.
    """
    cache.delete("site_settings_context")


def invalidate_cart_cache(request):
    """
    Call this function when cart is modified to clear the cart count cache.
    """
    cart_session_key = request.session.session_key
    if cart_session_key:
        cache.delete(f"cart_count_{cart_session_key}")
