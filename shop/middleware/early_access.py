from django.shortcuts import redirect
from django.urls import reverse


class EarlyAccessMiddleware:
    """
    Middleware to require an access code before viewing the site.
    Allows staff users and certain paths to bypass the lock.
    """

    # Paths that bypass the early access check
    ALLOWED_PATH_PREFIXES = (
        "/accounts/",           # Login/signup pages
        "/shop/early-access/",  # The unlock page itself
        "/bp-manage/",          # Admin panel
        "/bp-djadmin/",         # Django admin
        "/health/",             # Health checks
        "/shop/health/",        # Shop health checks
        "/shop/webhook/",       # Stripe/SMS webhooks
        "/shop/campaigns/",     # Campaign webhooks
        "/static/",             # Static files
        "/media/",              # Media files
        "/__reload__/",         # Django browser reload (dev)
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Import here to avoid circular imports
        from shop.models.settings import SiteSettings

        # Get site settings
        site_settings = SiteSettings.load()

        # Skip if early access is not enabled
        if not site_settings.early_access_enabled:
            return self.get_response(request)

        # Skip for staff users (unless include_staff is enabled)
        if request.user.is_authenticated and request.user.is_staff:
            if not site_settings.early_access_include_staff:
                return self.get_response(request)

        # Skip for allowed paths
        path = request.path
        if any(path.startswith(prefix) for prefix in self.ALLOWED_PATH_PREFIXES):
            return self.get_response(request)

        # Check if user has already verified
        if request.session.get("early_access_verified"):
            return self.get_response(request)

        # Store the original URL to redirect back after verification
        if not path.startswith("/shop/early-access/"):
            request.session["early_access_next"] = request.get_full_path()

        # Redirect to early access page
        return redirect("shop:early_access")
