from functools import wraps
from urllib.parse import quote

from django.conf import settings
from django.shortcuts import redirect

from django_otp import user_has_device


def two_factor_required(view_func):
    """
    Decorator to require 2FA verification for admin views.
    Only enforced when DEBUG=False (production mode).
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Skip 2FA check in debug mode
        if settings.DEBUG:
            return view_func(request, *args, **kwargs)

        # Check if user is authenticated
        if not request.user.is_authenticated:
            return redirect("/accounts/login/")

        # Check if user has 2FA enabled
        if not user_has_device(request.user):
            # Redirect to 2FA setup
            return redirect("two_factor_setup")

        # Check if 2FA is verified in this session
        if not request.session.get("2fa_verified"):
            # Redirect to 2FA verification with next parameter
            # URL-encode the path to prevent injection attacks
            next_url = quote(request.get_full_path(), safe='')
            return redirect(f"/bp-manage/2fa/verify/?next={next_url}")

        # User is authenticated and 2FA verified
        return view_func(request, *args, **kwargs)

    return wrapper
