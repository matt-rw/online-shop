from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-8gpylib_d)h$q7mk&m4=sqe9*mpkt@ptq7^k2q$=%0nsfx$%kc"

# SECURITY WARNING: define the correct hosts in production!
ALLOWED_HOSTS = ["*"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# DJANGO BROWSER RELOAD
# INSTALLED_APPS += ['django_browser_reload']
# MIDDLEWARE += ['django_browser_reload.middleware.BrowserReloadMiddleware']


try:
    from .local import *
except ImportError:
    pass
