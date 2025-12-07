from django.shortcuts import render

from shop.models import Product
from shop.models.settings import SiteSettings


def home_page(request):
    """Render the home page."""
    site_settings = SiteSettings.load()

    # Get featured products for the homepage
    featured_products = Product.objects.filter(
        is_active=True,
        featured=True
    ).select_related('category_obj').prefetch_related('variants')[:4]

    context = {
        "site_settings": site_settings,
        "featured_products": featured_products,
    }
    return render(request, "home/home_page.html", context)
