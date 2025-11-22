from django.shortcuts import render

from shop.models.settings import SiteSettings


def home_page(request):
    """Render the home page."""
    site_settings = SiteSettings.load()
    context = {
        "site_settings": site_settings,
    }
    return render(request, "home/home_page.html", context)
