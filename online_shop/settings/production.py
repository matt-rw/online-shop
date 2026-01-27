import os

import dj_database_url

from .base import *

DEBUG = False

# Sentry Error Monitoring
# Get Sentry DSN from environment variable (set in Render dashboard)
SENTRY_DSN = os.environ.get("SENTRY_DSN")

if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        # Performance monitoring - captures 10% of transactions
        traces_sample_rate=0.1,
        # Capture errors
        send_default_pii=False,  # Don't send user data for privacy
        # Environment info
        environment="production",
        # Release tracking (helps identify which deploy broke things)
        release=os.environ.get("RENDER_GIT_COMMIT", "unknown")[:7],
    )

SECRET_KEY = get_env_variable("SECRET_KEY")

ALLOWED_HOSTS = [".onrender.com", "blueprnt.store", "www.blueprnt.store"]

# Security settings
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# CSRF trusted origins for your domains
CSRF_TRUSTED_ORIGINS = [
    "https://*.onrender.com",
    "https://blueprnt.store",
    "https://www.blueprnt.store",
]

# Static files - use WhiteNoise for efficient serving
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

# Use WhiteNoise's compressed static file storage
STORAGES["staticfiles"]["BACKEND"] = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Enable Brotli and Gzip compression for static files
WHITENOISE_COMPRESS = True
WHITENOISE_USE_FINDERS = False

# Database - PostgreSQL for production
# Render automatically provides DATABASE_URL environment variable
DATABASE_URL = get_env_variable("DATABASE_URL", None)

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    # Fallback to SQLite if DATABASE_URL not set (shouldn't happen in production)
    pass

# Logging configuration for production
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

try:
    from .local import *
except ImportError:
    pass
