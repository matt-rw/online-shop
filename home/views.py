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
    hero_slides = []
    for s in all_slides:
        if s.get('is_active', True):
            # Ensure position keys exist with defaults
            s.setdefault('zoom', 100)
            s.setdefault('position_x', 50)
            s.setdefault('position_y', 50)
            s.setdefault('mobile_zoom', s.get('zoom', 100))
            s.setdefault('mobile_position_x', s.get('position_x', 50))
            s.setdefault('mobile_position_y', s.get('position_y', 50))
            hero_slides.append(s)

    # Get gallery images and ensure position keys exist
    gallery_images = []
    for img in (site_settings.gallery_images or []):
        img.setdefault('zoom', 100)
        img.setdefault('position_x', 50)
        img.setdefault('position_y', 50)
        gallery_images.append(img)

    # Get slideshow settings with defaults
    slideshow_settings = site_settings.slideshow_settings or {}
    slideshow_settings.setdefault('duration', 5000)
    slideshow_settings.setdefault('autoplay', True)
    slideshow_settings.setdefault('transition', 'fade')

    context = {
        "site_settings": site_settings,
        "featured_products": featured_products,
        "hero_slides": hero_slides,
        "gallery_images": gallery_images,
        "slideshow_settings": slideshow_settings,
    }
    return render(request, "home/home_page.html", context)
