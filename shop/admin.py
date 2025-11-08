from django.contrib import admin
from django.utils.html import format_html

from .models import Color, Product, ProductVariant, Size, EmailSubscription


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'base_price', 'is_active')


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ('product', 'size', 'color', 'price', 'stock_quantity')
    list_filter = ('size', 'color')


@admin.register(EmailSubscription)
class EmailSubscriptionAdmin(admin.ModelAdmin):
    """
    Admin interface for managing email subscriptions.
    Shows subscriber emails with confirmation status and dates.
    """
    list_display = ('email', 'status_badge', 'subscribed_at', 'source')
    list_filter = ('is_confirmed', 'source', 'subscribed_at')
    search_fields = ('email',)
    readonly_fields = ('subscribed_at', 'confirmed_at', 'source')
    date_hierarchy = 'subscribed_at'

    # Enable CSV export
    actions = ['export_as_csv']

    def status_badge(self, obj):
        """Display confirmation status with colored badge."""
        if obj.is_confirmed:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">✓ Confirmed</span>'
            )
        return format_html(
            '<span style="background-color: #ffc107; color: black; padding: 3px 10px; border-radius: 3px; font-weight: bold;">⏳ Pending</span>'
        )
    status_badge.short_description = 'Status'

    def export_as_csv(self, request, queryset):
        """Export selected subscribers to CSV file."""
        import csv
        from django.http import HttpResponse
        from datetime import datetime

        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="subscribers_{datetime.now().strftime("%Y%m%d")}.csv"'

        writer = csv.writer(response)
        writer.writerow(['Email', 'Confirmed', 'Subscribed Date', 'Source'])

        for subscription in queryset:
            writer.writerow([
                subscription.email,
                'Yes' if subscription.is_confirmed else 'No',
                subscription.subscribed_at.strftime('%Y-%m-%d %H:%M'),
                subscription.source
            ])

        return response
    export_as_csv.short_description = "Export selected to CSV"

    def get_queryset(self, request):
        """Order by most recent first."""
        qs = super().get_queryset(request)
        return qs.order_by('-subscribed_at')


admin.site.register(Size)
admin.site.register(Color)
