from .base import *
import dj_database_url

DEBUG = False

SECRET_KEY = get_env_variable('SECRET_KEY')

ALLOWED_HOSTS = ['.onrender.com', 'blueprintapparel.store', 'www.blueprintapparel.store']

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
    'https://*.onrender.com',
    'https://blueprintapparel.store',
    'https://www.blueprintapparel.store',
]

# Wagtail admin base URL for production
WAGTAILADMIN_BASE_URL = "https://blueprintapparel.store"

# Static files - use WhiteNoise for efficient serving
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

# Use WhiteNoise's compressed static file storage
STORAGES["staticfiles"]["BACKEND"] = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Database - PostgreSQL for production
# Render automatically provides DATABASE_URL environment variable
DATABASE_URL = get_env_variable('DATABASE_URL', None)

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(
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
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}

try:
    from .local import *
except ImportError:
    pass
