from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# Use local memory cache for development (no Redis required)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "default",
    },
    "sessions": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "sessions",
    },
    "templates": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "templates",
    },
    "database": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "database",
    },
}

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = get_env_variable("SECRET_KEY", "django-insecure-dev-fallback-key-change-in-env-file")

# SECURITY WARNING: define the correct hosts in production!
ALLOWED_HOSTS = ["*"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# DJANGO BROWSER RELOAD
INSTALLED_APPS += ["django_browser_reload"]
MIDDLEWARE += ["django_browser_reload.middleware.BrowserReloadMiddleware"]

try:
    from .local import *
except ImportError:
    pass
