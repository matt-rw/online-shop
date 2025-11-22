"""
Signal handlers for shop app.
"""

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .cart_utils import merge_carts


@receiver(user_logged_in)
def merge_cart_on_login(sender, request, user, **kwargs):
    """
    Merge anonymous cart into user's cart when they log in.
    """
    session_key = request.session.session_key
    if session_key:
        merge_carts(user, session_key)
