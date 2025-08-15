from django.db import models
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.fields import RichTextField
from wagtail.models import Orderable, Page

from .models import Product


class ShopIndexPage(Page):
    """
    A Wagtail Page model that serves as the landing page for the online shop.

    This page acts as a container for all ProductPage instances. It includes an
    introductory rich text area and renders a list of child product pages.

    Example URL: /shop/
    """
    intro = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel('intro'),
    ]

    subpage_types = ['shop.ProductPage']


class ProductPage(Page):
    """
    A Wagtail Page model representing the CMS/visual layout of a product.

    Each product has a description, price, and an optional collection
    of images. It is intended to be created as a child of ShopIndexPage.

    Example URL: /shop/sample-product/
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='pages'
    )
    description = RichTextField()
    # price = models.DecimalField(max_digits=10, decimal_places=2)

    content_panels = Page.content_panels + [
        FieldPanel('product'),
        FieldPanel('description'),
        # FieldPanel('price'),
        InlinePanel('product_images', label="Product Images"),
    ]

    parent_page_types = ['shop.ShopIndexPage']


class ProductImage(Orderable):
    """
    An orderable model for storing images related to a ProductPage.

    Allows multiple images per product with optional captions. Images
    are displayed in the order defined by the content editor using
    drag-and-drop.

    This model is edited inline within the ProductPage admin interface.
    """
    page = ParentalKey(
        'shop.ProductPage',
        on_delete=models.CASCADE,
        related_name='product_images'
    )
    image = models.ForeignKey(
        'wagtailimages.Image',
        on_delete=models.CASCADE,
        related_name='+',
    )
    caption = models.CharField(blank=True, max_length=250)

    panels = [
        FieldPanel('image'),
        FieldPanel('caption'),
    ]
