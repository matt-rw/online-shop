"""
Caching utilities for customer-facing performance optimization.

This module provides caching for the production site to improve page load times,
reduce database queries, and enhance the customer experience.

Focus areas:
- Product catalog and detail pages
- Homepage hero and featured content
- Shopping cart operations
- Site settings and navigation

See PERFORMANCE_OPTIMIZATIONS.md for usage examples and benchmarks.
"""

import functools
import logging
from typing import Any, Callable, Optional

from django.core.cache import cache, caches
from django.db.models import Model, Prefetch, QuerySet
from django.db.models.signals import post_delete, post_save

from online_shop.settings.cache import CacheKeys, CacheTimeouts

logger = logging.getLogger(__name__)


def cache_model_instance(
    timeout: int = CacheTimeouts.TEN_MINUTES,
    key_prefix: str = "model",
    cache_alias: str = "default",
) -> Callable:
    """
    Decorator to cache a function that returns a model instance or queryset.

    Args:
        timeout: Cache timeout in seconds
        key_prefix: Prefix for the cache key
        cache_alias: Which cache backend to use

    Example:
        @cache_model_instance(timeout=3600, key_prefix='product')
        def get_product_by_slug(slug):
            return Product.objects.select_related().get(slug=slug)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            key_parts = [key_prefix, func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)

            # Try to get from cache
            cached_value = caches[cache_alias].get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache HIT: {cache_key}")
                return cached_value

            # Cache miss - call the function
            logger.debug(f"Cache MISS: {cache_key}")
            result = func(*args, **kwargs)

            # Cache the result
            if result is not None:
                caches[cache_alias].set(cache_key, result, timeout)

            return result

        # Add cache clearing method
        def clear_cache(*args, **kwargs):
            """Clear the cache for this function with given arguments."""
            key_parts = [key_prefix, func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)
            caches[cache_alias].delete(cache_key)
            logger.info(f"Cache CLEARED: {cache_key}")

        wrapper.clear_cache = clear_cache
        return wrapper

    return decorator


def invalidate_on_save(*models: Model) -> Callable:
    """
    Decorator to automatically invalidate cache when specified models are saved.

    Critical for keeping product data fresh when inventory changes.

    Args:
        *models: Model classes to watch for changes

    Example:
        @invalidate_on_save(Product, ProductVariant)
        @cache_model_instance(timeout=3600)
        def get_featured_products():
            return Product.objects.filter(is_featured=True)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # Connect signal handlers
        def invalidate_cache(sender, **kwargs):
            if hasattr(wrapper, "clear_cache"):
                wrapper.clear_cache()

        for model in models:
            post_save.connect(invalidate_cache, sender=model, weak=False)
            post_delete.connect(invalidate_cache, sender=model, weak=False)

        return wrapper

    return decorator


class CachedQuerySet:
    """
    Helper class to cache expensive querysets.

    Perfect for product listings with complex joins and filters.

    Example:
        # Cache active products with all variants
        cached_products = CachedQuerySet(
            queryset=Product.objects.filter(is_active=True).prefetch_related('variants'),
            cache_key='products:active:with_variants',
            timeout=600
        )
        products = cached_products.get()
    """

    def __init__(
        self,
        queryset: QuerySet,
        cache_key: str,
        timeout: int = CacheTimeouts.TEN_MINUTES,
        cache_alias: str = "database",
    ):
        self.queryset = queryset
        self.cache_key = cache_key
        self.timeout = timeout
        self.cache_alias = cache_alias

    def get(self, force_refresh: bool = False) -> QuerySet:
        """
        Get the queryset from cache or database.

        Args:
            force_refresh: If True, bypass cache and fetch from database

        Returns:
            QuerySet results
        """
        if force_refresh:
            return self._fetch_and_cache()

        cached_value = caches[self.cache_alias].get(self.cache_key)
        if cached_value is not None:
            logger.debug(f"QuerySet cache HIT: {self.cache_key}")
            return cached_value

        logger.debug(f"QuerySet cache MISS: {self.cache_key}")
        return self._fetch_and_cache()

    def _fetch_and_cache(self) -> QuerySet:
        """Fetch from database and update cache."""
        # Evaluate queryset to a list to cache the results
        results = list(self.queryset)
        caches[self.cache_alias].set(self.cache_key, results, self.timeout)
        return results

    def invalidate(self) -> None:
        """Clear this queryset from cache."""
        caches[self.cache_alias].delete(self.cache_key)
        logger.info(f"QuerySet cache CLEARED: {self.cache_key}")


def get_or_set_cache(
    key: str,
    default_callable: Callable,
    timeout: int = CacheTimeouts.FIVE_MINUTES,
    cache_alias: str = "default",
) -> Any:
    """
    Get value from cache or set it using the callable if not found.

    Args:
        key: Cache key
        default_callable: Function to call if cache miss
        timeout: Cache timeout in seconds
        cache_alias: Which cache backend to use

    Returns:
        Cached or newly computed value

    Example:
        # Cache site settings
        settings = get_or_set_cache(
            key=CacheKeys.SITE_SETTINGS,
            default_callable=lambda: SiteSettings.objects.first(),
            timeout=CacheTimeouts.ONE_HOUR
        )
    """
    cached_value = caches[cache_alias].get(key)

    if cached_value is not None:
        logger.debug(f"Cache HIT: {key}")
        return cached_value

    logger.debug(f"Cache MISS: {key}")
    value = default_callable()
    caches[cache_alias].set(key, value, timeout)
    return value


def warm_customer_cache():
    """
    Pre-populate cache with data that improves customer experience.

    Call this:
    - On application startup
    - After deploying product changes
    - Via management command: python manage.py warm_cache

    Focuses on:
    - Active products (catalog pages load faster)
    - Site settings (navigation, hero images)
    - Featured/popular items
    """
    from shop.models import Product, SiteSettings

    logger.info("Warming customer-facing cache...")

    try:
        # Cache active products with variants (for catalog pages)
        # This is the most expensive query on product listing pages
        products = list(
            Product.objects.filter(is_active=True)
            .select_related()
            .prefetch_related("variants", "variants__size", "variants__color")
        )
        cache.set(CacheKeys.PRODUCT_LIST, products, CacheTimeouts.TEN_MINUTES)
        logger.info(f"Cached {len(products)} active products")

        # Cache individual products by slug (for detail pages)
        for product in products:
            cache.set(CacheKeys.product_detail(product.slug), product, CacheTimeouts.TEN_MINUTES)

        # Cache site settings (used on every page - hero image, nav, footer)
        settings = SiteSettings.objects.first()
        if settings:
            cache.set(CacheKeys.SITE_SETTINGS, settings, CacheTimeouts.ONE_HOUR)
            logger.info("Cached site settings")

        logger.info("Customer cache warming complete ✓")

    except Exception as e:
        logger.error(f"Error warming cache: {e}", exc_info=True)


def clear_product_cache():
    """
    Clear all product-related cache.

    Call this when:
    - Products are updated
    - Inventory changes
    - Prices change
    """
    logger.info("Clearing product cache...")
    cache.delete(CacheKeys.PRODUCT_LIST)
    # Clear pattern-based keys would require redis-specific commands
    logger.info("Product cache cleared")


def clear_all_cache():
    """
    Clear all cache. Use with caution in production!

    Better to clear specific caches (like clear_product_cache) rather than everything.
    """
    logger.warning("Clearing ALL cache data")
    cache.clear()
    logger.info("All cache cleared")
