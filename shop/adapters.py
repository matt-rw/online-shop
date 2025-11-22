from allauth.account.adapter import DefaultAccountAdapter
from django.urls import reverse


class CustomAccountAdapter(DefaultAccountAdapter):
    """Custom adapter to redirect staff users to admin after login."""

    def get_login_redirect_url(self, request):
        """
        Redirect staff users to admin dashboard, regular users to home.
        """
        if request.user.is_staff:
            return reverse('admin_home')
        return super().get_login_redirect_url(request)
