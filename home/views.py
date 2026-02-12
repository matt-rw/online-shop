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

    # Get hero slides (use database slides if available, otherwise use defaults)
    # Filter to only show active slides (is_active defaults to True if not set)
    all_slides = site_settings.hero_slides or []
    hero_slides = [s for s in all_slides if s.get('is_active', True)]

    context = {
        "site_settings": site_settings,
        "featured_products": featured_products,
        "hero_slides": hero_slides,
    }
    return render(request, "home/home_page.html", context)
