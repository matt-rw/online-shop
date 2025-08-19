from django.contrib import admin

from .models import Color, Product, ProductVariant, Size


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'base_price', 'is_active')


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ('product', 'size', 'color', 'price', 'stock_quantity')
    list_filter = ('size', 'color')


admin.site.register(Size)
admin.site.register(Color)
