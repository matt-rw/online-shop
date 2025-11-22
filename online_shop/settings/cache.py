"""
Caching Configuration for Django Application

This module configures Redis-based caching for improved performance.
See PERFORMANCE_OPTIMIZATIONS.md for detailed documentation.
"""

import os


def get_cache_config():
    """
    Get cache configuration based on environment.

    Returns:
        dict: Cache configuration for Django CACHES setting
    """
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    return {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": redis_url,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "PARSER_CLASS": "redis.connection.HiredisParser",
                "CONNECTION_POOL_KWARGS": {
                    "max_connections": 50,
                    "retry_on_timeout": True,
                },
                "SOCKET_CONNECT_TIMEOUT": 5,
                "SOCKET_TIMEOUT": 5,
            },
            "KEY_PREFIX": "blueprint",
            "TIMEOUT": 300,  # 5 minutes default
        },
        # Separate cache for sessions (longer timeout)
        "sessions": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": redis_url,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "PARSER_CLASS": "redis.connection.HiredisParser",
            },
            "KEY_PREFIX": "blueprint_session",
            "TIMEOUT": 86400,  # 24 hours
        },
        # Cache for templates and static content
        "templates": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": redis_url,
            "KEY_PREFIX": "blueprint_template",
            "TIMEOUT": 3600,  # 1 hour
        },
        # Cache for database queries
        "database": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": redis_url,
            "KEY_PREFIX": "blueprint_db",
            "TIMEOUT": 600,  # 10 minutes
        },
    }


# Cache key patterns for consistency
class CacheKeys:
    """Centralized cache key definitions to prevent typos and conflicts."""

    # Product caching
    PRODUCT_LIST = "products:list:all"
    PRODUCT_DETAIL = "products:detail:{slug}"
    PRODUCT_VARIANTS = "products:variants:{product_id}"

    # Subscription stats
    EMAIL_SUBSCRIBER_COUNT = "stats:email_subscribers:count"
    SMS_SUBSCRIBER_COUNT = "stats:sms_subscribers:count"
    ACTIVE_CAMPAIGNS = "campaigns:active:list"

    # Site settings
    SITE_SETTINGS = "site:settings"

    # Analytics
    PAGE_VIEW_COUNT = "analytics:pageviews:{path}:count"
    VISITOR_COUNT_TODAY = "analytics:visitors:today:count"

    # Email templates
    EMAIL_TEMPLATE = "email:template:{template_id}"
    SMS_TEMPLATE = "sms:template:{template_id}"

    @staticmethod
    def product_detail(slug: str) -> str:
        """Generate cache key for product detail."""
        return CacheKeys.PRODUCT_DETAIL.format(slug=slug)

    @staticmethod
    def product_variants(product_id: int) -> str:
        """Generate cache key for product variants."""
        return CacheKeys.PRODUCT_VARIANTS.format(product_id=product_id)

    @staticmethod
    def email_template(template_id: int) -> str:
        """Generate cache key for email template."""
        return CacheKeys.EMAIL_TEMPLATE.format(template_id=template_id)

    @staticmethod
    def sms_template(template_id: int) -> str:
        """Generate cache key for SMS template."""
        return CacheKeys.SMS_TEMPLATE.format(template_id=template_id)

    @staticmethod
    def page_view_count(path: str) -> str:
        """Generate cache key for page view count."""
        return CacheKeys.PAGE_VIEW_COUNT.format(path=path)


# Cache timeout constants (in seconds)
class CacheTimeouts:
    """Centralized cache timeout definitions."""

    ONE_MINUTE = 60
    FIVE_MINUTES = 300
    TEN_MINUTES = 600
    THIRTY_MINUTES = 1800
    ONE_HOUR = 3600
    SIX_HOURS = 21600
    ONE_DAY = 86400
    ONE_WEEK = 604800
