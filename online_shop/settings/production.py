from .base import *

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
# Uncomment and configure when ready to switch from SQLite
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': get_env_variable('DB_NAME'),
#         'USER': get_env_variable('DB_USER'),
#         'PASSWORD': get_env_variable('DB_PASSWORD'),
#         'HOST': get_env_variable('DB_HOST'),
#         'PORT': get_env_variable('DB_PORT', '5432'),
#     }
# }

try:
    from .local import *
except ImportError:
    pass
