from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    Campaign,
    CampaignMessage,
    Color,
    EmailCampaign,
    EmailLog,
    EmailSubscription,
    EmailTemplate,
    Expense,
    ExpenseCategory,
    PageView,
    Product,
    ProductVariant,
    Revenue,
    SiteSettings,
    Size,
    SMSCampaign,
    SMSLog,
    SMSSubscription,
    SMSTemplate,
    VisitorSession,
)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "base_price", "is_active")


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ("product", "size", "color", "price", "stock_quantity")
    list_filter = ("size", "color")


@admin.register(EmailSubscription)
class EmailSubscriptionAdmin(admin.ModelAdmin):
    """
    Admin interface for managing email subscriptions.
    Shows subscriber emails with confirmation status and dates.
    """

    list_display = ("email", "status_badge", "active_badge", "subscribed_at", "source")
    list_filter = ("is_confirmed", "is_active", "source", "subscribed_at")
    search_fields = ("email",)
    readonly_fields = ("subscribed_at", "confirmed_at", "unsubscribed_at", "source")
    date_hierarchy = "subscribed_at"
    actions = ["export_as_csv", "mark_as_active", "mark_as_inactive"]

    def status_badge(self, obj):
        """Display confirmation status with colored badge."""
        if obj.is_confirmed:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">✓ Confirmed</span>'
            )
        return format_html(
            '<span style="background-color: #ffc107; color: black; padding: 3px 10px; border-radius: 3px; font-weight: bold;">⏳ Pending</span>'
        )

    status_badge.short_description = "Status"

    def active_badge(self, obj):
        """Display active/inactive status."""
        if obj.is_active:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px;">Active</span>'
            )
        return format_html(
            '<span style="background-color: #dc3545; color: white; padding: 3px 10px; border-radius: 3px;">Inactive</span>'
        )

    active_badge.short_description = "Active"

    def export_as_csv(self, request, queryset):
        """Export selected subscribers to CSV file."""
        import csv
        from datetime import datetime

        from django.http import HttpResponse

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="email_subscribers_{datetime.now().strftime("%Y%m%d")}.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(["Email", "Confirmed", "Active", "Subscribed Date", "Source"])

        for subscription in queryset:
            writer.writerow(
                [
                    subscription.email,
                    "Yes" if subscription.is_confirmed else "No",
                    "Yes" if subscription.is_active else "No",
                    subscription.subscribed_at.strftime("%Y-%m-%d %H:%M"),
                    subscription.source,
                ]
            )

        return response

    export_as_csv.short_description = "Export selected to CSV"

    def mark_as_active(self, request, queryset):
        """Mark selected subscriptions as active."""
        updated = queryset.update(is_active=True, unsubscribed_at=None)
        self.message_user(request, f"{updated} subscription(s) marked as active.")

    mark_as_active.short_description = "Mark as active"

    def mark_as_inactive(self, request, queryset):
        """Mark selected subscriptions as inactive."""
        updated = queryset.update(is_active=False, unsubscribed_at=timezone.now())
        self.message_user(request, f"{updated} subscription(s) marked as inactive.")

    mark_as_inactive.short_description = "Mark as inactive"

    def get_queryset(self, request):
        """Order by most recent first."""
        qs = super().get_queryset(request)
        return qs.order_by("-subscribed_at")


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    """Admin interface for managing email templates."""

    list_display = (
        "name",
        "template_type",
        "auto_trigger",
        "is_active",
        "times_used",
        "updated_at",
    )
    list_filter = ("template_type", "auto_trigger", "is_active", "created_at")
    search_fields = ("name", "subject", "html_body")
    readonly_fields = ("times_used", "created_at", "updated_at", "created_by")
    fieldsets = (
        (
            "Template Information",
            {"fields": ("name", "template_type", "auto_trigger", "is_active")},
        ),
        (
            "Email Content",
            {
                "fields": ("subject", "html_body", "text_body"),
                "description": 'Use {variable_name} for dynamic content. Example: "Hi {first_name}, welcome to Blueprint!"',
            },
        ),
        (
            "Metadata",
            {
                "fields": ("times_used", "created_at", "updated_at", "created_by"),
                "classes": ("collapse",),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        """Automatically set created_by to current user."""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(EmailCampaign)
class EmailCampaignAdmin(admin.ModelAdmin):
    """Admin interface for managing email campaigns."""

    list_display = ("name", "template", "status_badge", "scheduled_at", "progress", "created_at")
    list_filter = ("status", "created_at", "scheduled_at")
    search_fields = ("name", "notes")
    readonly_fields = (
        "total_recipients",
        "sent_count",
        "failed_count",
        "started_at",
        "completed_at",
        "created_at",
        "created_by",
    )
    date_hierarchy = "created_at"
    actions = ["send_now", "cancel_campaign"]

    fieldsets = (
        ("Campaign Information", {"fields": ("name", "template", "status")}),
        ("Targeting", {"fields": ("send_to_all_active",)}),
        ("Scheduling", {"fields": ("scheduled_at",)}),
        (
            "Progress",
            {
                "fields": (
                    "total_recipients",
                    "sent_count",
                    "failed_count",
                    "started_at",
                    "completed_at",
                ),
                "classes": ("collapse",),
            },
        ),
        ("Notes", {"fields": ("notes", "created_at", "created_by"), "classes": ("collapse",)}),
    )

    def status_badge(self, obj):
        """Display campaign status with colored badge."""
        colors = {
            "draft": "#6c757d",
            "scheduled": "#ffc107",
            "sending": "#17a2b8",
            "sent": "#28a745",
            "paused": "#fd7e14",
            "cancelled": "#dc3545",
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def progress(self, obj):
        """Display campaign progress."""
        if obj.total_recipients == 0:
            return "-"
        percentage = (
            (obj.sent_count / obj.total_recipients) * 100 if obj.total_recipients > 0 else 0
        )
        return format_html(
            "{}/{} ({}%)", obj.sent_count, obj.total_recipients, round(percentage, 1)
        )

    progress.short_description = "Progress"

    def send_now(self, request, queryset):
        """Send selected campaigns immediately."""
        from shop.utils.email_helper import send_campaign

        for campaign in queryset:
            if campaign.status in ["draft", "scheduled"]:
                result = send_campaign(campaign)
                if "error" in result:
                    self.message_user(
                        request,
                        f'Campaign {campaign.name} failed: {result["error"]}',
                        level="ERROR",
                    )
                else:
                    self.message_user(
                        request,
                        f'Campaign {campaign.name} completed. Sent: {result["sent"]}, Failed: {result["failed"]}',
                    )
            else:
                self.message_user(
                    request,
                    f"Campaign {campaign.name} cannot be sent (status: {campaign.status})",
                    level="WARNING",
                )

    send_now.short_description = "Send selected campaigns now"

    def cancel_campaign(self, request, queryset):
        """Cancel selected campaigns."""
        updated = queryset.filter(status__in=["draft", "scheduled"]).update(status="cancelled")
        self.message_user(request, f"{updated} campaign(s) cancelled.")

    cancel_campaign.short_description = "Cancel selected campaigns"

    def save_model(self, request, obj, form, change):
        """Automatically set created_by to current user."""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    """Admin interface for viewing email logs."""

    list_display = ("email_address", "subject", "status_badge", "campaign", "template", "sent_at")
    list_filter = ("status", "sent_at", "campaign", "template")
    search_fields = ("email_address", "subject")
    readonly_fields = (
        "subscription",
        "email_address",
        "subject",
        "html_body",
        "text_body",
        "campaign",
        "template",
        "status",
        "sent_at",
        "delivered_at",
        "error_message",
    )
    date_hierarchy = "sent_at"

    def status_badge(self, obj):
        """Display email status with colored badge."""
        colors = {
            "queued": "#6c757d",
            "sent": "#17a2b8",
            "delivered": "#28a745",
            "failed": "#dc3545",
            "bounced": "#ffc107",
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def has_add_permission(self, request):
        """Disable adding logs manually."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow deletion for cleanup."""
        return True


@admin.register(SMSSubscription)
class SMSSubscriptionAdmin(admin.ModelAdmin):
    """Admin interface for managing SMS subscriptions."""

    list_display = ("phone_number", "status_badge", "active_badge", "subscribed_at", "source")
    list_filter = ("is_confirmed", "is_active", "source", "subscribed_at")
    search_fields = ("phone_number",)
    readonly_fields = ("subscribed_at", "confirmed_at", "unsubscribed_at", "source")
    date_hierarchy = "subscribed_at"
    actions = ["export_as_csv", "mark_as_active", "mark_as_inactive"]

    def status_badge(self, obj):
        """Display confirmation status with colored badge."""
        if obj.is_confirmed:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">✓ Confirmed</span>'
            )
        return format_html(
            '<span style="background-color: #ffc107; color: black; padding: 3px 10px; border-radius: 3px; font-weight: bold;">⏳ Pending</span>'
        )

    status_badge.short_description = "Status"

    def active_badge(self, obj):
        """Display active/inactive status."""
        if obj.is_active:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px;">Active</span>'
            )
        return format_html(
            '<span style="background-color: #dc3545; color: white; padding: 3px 10px; border-radius: 3px;">Inactive</span>'
        )

    active_badge.short_description = "Active"

    def export_as_csv(self, request, queryset):
        """Export selected subscribers to CSV."""
        import csv
        from datetime import datetime

        from django.http import HttpResponse

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="sms_subscribers_{datetime.now().strftime("%Y%m%d")}.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(["Phone Number", "Confirmed", "Active", "Subscribed Date", "Source"])

        for subscription in queryset:
            writer.writerow(
                [
                    subscription.phone_number,
                    "Yes" if subscription.is_confirmed else "No",
                    "Yes" if subscription.is_active else "No",
                    subscription.subscribed_at.strftime("%Y-%m-%d %H:%M"),
                    subscription.source,
                ]
            )

        return response

    export_as_csv.short_description = "Export selected to CSV"

    def mark_as_active(self, request, queryset):
        """Mark selected subscriptions as active."""
        updated = queryset.update(is_active=True, unsubscribed_at=None)
        self.message_user(request, f"{updated} subscription(s) marked as active.")

    mark_as_active.short_description = "Mark as active"

    def mark_as_inactive(self, request, queryset):
        """Mark selected subscriptions as inactive."""
        updated = queryset.update(is_active=False, unsubscribed_at=timezone.now())
        self.message_user(request, f"{updated} subscription(s) marked as inactive.")

    mark_as_inactive.short_description = "Mark as inactive"


@admin.register(SMSTemplate)
class SMSTemplateAdmin(admin.ModelAdmin):
    """Admin interface for managing SMS templates."""

    list_display = (
        "name",
        "template_type",
        "auto_trigger",
        "is_active",
        "times_used",
        "updated_at",
    )
    list_filter = ("template_type", "auto_trigger", "is_active", "created_at")
    search_fields = ("name", "message_body")
    readonly_fields = ("times_used", "created_at", "updated_at", "created_by")
    fieldsets = (
        (
            "Template Information",
            {"fields": ("name", "template_type", "auto_trigger", "is_active")},
        ),
        (
            "Message Content",
            {
                "fields": ("message_body",),
                "description": 'Use {variable_name} for dynamic content. Example: "Hi {first_name}, your code is {code}"',
            },
        ),
        (
            "Metadata",
            {
                "fields": ("times_used", "created_at", "updated_at", "created_by"),
                "classes": ("collapse",),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        """Automatically set created_by to current user."""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(SMSCampaign)
class SMSCampaignAdmin(admin.ModelAdmin):
    """Admin interface for managing SMS campaigns."""

    list_display = ("name", "template", "status_badge", "scheduled_at", "progress", "created_at")
    list_filter = ("status", "created_at", "scheduled_at")
    search_fields = ("name", "notes")
    readonly_fields = (
        "total_recipients",
        "sent_count",
        "failed_count",
        "started_at",
        "completed_at",
        "created_at",
        "created_by",
    )
    date_hierarchy = "created_at"
    actions = ["send_now", "cancel_campaign"]

    fieldsets = (
        ("Campaign Information", {"fields": ("name", "template", "status")}),
        ("Targeting", {"fields": ("send_to_all_active",)}),
        ("Scheduling", {"fields": ("scheduled_at",)}),
        (
            "Progress",
            {
                "fields": (
                    "total_recipients",
                    "sent_count",
                    "failed_count",
                    "started_at",
                    "completed_at",
                ),
                "classes": ("collapse",),
            },
        ),
        ("Notes", {"fields": ("notes", "created_at", "created_by"), "classes": ("collapse",)}),
    )

    def status_badge(self, obj):
        """Display campaign status with colored badge."""
        colors = {
            "draft": "#6c757d",
            "scheduled": "#ffc107",
            "sending": "#17a2b8",
            "sent": "#28a745",
            "paused": "#fd7e14",
            "cancelled": "#dc3545",
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def progress(self, obj):
        """Display campaign progress."""
        if obj.total_recipients == 0:
            return "-"
        percentage = (
            (obj.sent_count / obj.total_recipients) * 100 if obj.total_recipients > 0 else 0
        )
        return format_html(
            "{}/{} ({}%)", obj.sent_count, obj.total_recipients, round(percentage, 1)
        )

    progress.short_description = "Progress"

    def send_now(self, request, queryset):
        """Send selected campaigns immediately."""
        from shop.utils.twilio_helper import send_campaign

        for campaign in queryset:
            if campaign.status in ["draft", "scheduled"]:
                result = send_campaign(campaign)
                if "error" in result:
                    self.message_user(
                        request,
                        f'Campaign {campaign.name} failed: {result["error"]}',
                        level="ERROR",
                    )
                else:
                    self.message_user(
                        request,
                        f'Campaign {campaign.name} completed. Sent: {result["sent"]}, Failed: {result["failed"]}',
                    )
            else:
                self.message_user(
                    request,
                    f"Campaign {campaign.name} cannot be sent (status: {campaign.status})",
                    level="WARNING",
                )

    send_now.short_description = "Send selected campaigns now"

    def cancel_campaign(self, request, queryset):
        """Cancel selected campaigns."""
        updated = queryset.filter(status__in=["draft", "scheduled"]).update(status="cancelled")
        self.message_user(request, f"{updated} campaign(s) cancelled.")

    cancel_campaign.short_description = "Cancel selected campaigns"

    def save_model(self, request, obj, form, change):
        """Automatically set created_by to current user."""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    """Admin interface for viewing SMS logs."""

    list_display = ("phone_number", "status_badge", "campaign", "template", "sent_at")
    list_filter = ("status", "sent_at", "campaign", "template")
    search_fields = ("phone_number", "message_body", "twilio_sid")
    readonly_fields = (
        "subscription",
        "phone_number",
        "message_body",
        "campaign",
        "template",
        "status",
        "twilio_sid",
        "sent_at",
        "delivered_at",
        "error_message",
        "cost",
    )
    date_hierarchy = "sent_at"

    def status_badge(self, obj):
        """Display SMS status with colored badge."""
        colors = {
            "queued": "#6c757d",
            "sent": "#17a2b8",
            "delivered": "#28a745",
            "failed": "#dc3545",
            "undelivered": "#ffc107",
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def has_add_permission(self, request):
        """Disable adding logs manually."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow deletion for cleanup."""
        return True


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    """Admin interface for site-wide settings."""

    fieldsets = (
        ("Homepage Hero", {"fields": ("hero_image", "hero_title", "hero_subtitle")}),
        ("Site Information", {"fields": ("site_name", "site_description")}),
        ("Contact Information", {"fields": ("contact_email", "contact_phone")}),
        (
            "Social Media",
            {"fields": ("facebook_url", "instagram_url", "twitter_url", "discord_url")},
        ),
        ("Features", {"fields": ("maintenance_mode",)}),
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        # Only allow one instance
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion
        return False


admin.site.register(Size)
admin.site.register(Color)


@admin.register(PageView)
class PageViewAdmin(admin.ModelAdmin):
    """Admin interface for page view analytics."""

    list_display = ("path", "device_type", "browser", "referrer_domain", "ip_address", "viewed_at")
    list_filter = ("device_type", "browser", "os", "viewed_at")
    search_fields = ("path", "ip_address", "referrer_domain")
    readonly_fields = (
        "path",
        "method",
        "ip_address",
        "user_agent",
        "referrer",
        "referrer_domain",
        "device_type",
        "browser",
        "os",
        "viewed_at",
        "response_time_ms",
        "session_id",
    )
    date_hierarchy = "viewed_at"

    def has_add_permission(self, request):
        # These are created automatically by middleware
        return False


@admin.register(VisitorSession)
class VisitorSessionAdmin(admin.ModelAdmin):
    """Admin interface for visitor session analytics."""

    list_display = (
        "session_id_short",
        "page_views",
        "device_type",
        "landing_page",
        "first_seen",
        "last_seen",
    )
    list_filter = ("device_type", "first_seen")
    search_fields = ("session_id", "ip_address", "landing_page")
    readonly_fields = (
        "session_id",
        "first_seen",
        "landing_page",
        "referrer",
        "last_seen",
        "page_views",
        "ip_address",
        "user_agent",
        "device_type",
    )
    date_hierarchy = "first_seen"

    def session_id_short(self, obj):
        return f"{obj.session_id[:12]}..."

    session_id_short.short_description = "Session ID"

    def has_add_permission(self, request):
        # These are created automatically by middleware
        return False


class CampaignMessageInline(admin.TabularInline):
    model = CampaignMessage
    extra = 0
    fields = ("name", "message_type", "trigger_type", "delay_days", "status", "order")
    readonly_fields = ("sent_count", "failed_count")


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    """Admin interface for marketing campaigns."""

    list_display = (
        "name",
        "status",
        "target_group",
        "total_messages",
        "sent_messages",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("name", "description", "target_group")
    readonly_fields = (
        "created_at",
        "updated_at",
        "started_at",
        "completed_at",
        "total_messages",
        "sent_messages",
    )
    inlines = [CampaignMessageInline]

    fieldsets = (
        ("Campaign Details", {"fields": ("name", "description", "status", "target_group")}),
        ("Timestamps", {"fields": ("created_at", "updated_at", "started_at", "completed_at")}),
        ("Stats", {"fields": ("total_messages", "sent_messages")}),
    )


@admin.register(CampaignMessage)
class CampaignMessageAdmin(admin.ModelAdmin):
    """Admin interface for campaign messages."""

    list_display = ("name", "campaign", "message_type", "trigger_type", "status", "order")
    list_filter = ("message_type", "status", "trigger_type")
    search_fields = ("name", "campaign__name")
    readonly_fields = ("created_at", "updated_at", "sent_at", "sent_count", "failed_count")


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    """Admin interface for expense categories."""

    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    """Admin interface for tracking expenses."""

    list_display = ("description", "category", "amount", "date", "status_badge", "vendor")
    list_filter = ("category", "status", "payment_method", "date")
    search_fields = ("description", "vendor", "notes")
    readonly_fields = ("created_at", "updated_at", "created_by")
    date_hierarchy = "date"

    fieldsets = (
        ("Expense Information", {"fields": ("category", "amount", "description", "notes")}),
        ("Date and Status", {"fields": ("date", "status")}),
        ("Payment Details", {"fields": ("payment_method", "vendor")}),
        ("Order Linkage", {"fields": ("related_order",), "description": "Link shipping costs to specific orders"}),
        ("Receipt", {"fields": ("receipt",)}),
        ("Metadata", {"fields": ("created_by", "created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def status_badge(self, obj):
        """Display status with colored badge."""
        colors = {
            "pending": "#ffc107",
            "paid": "#28a745",
            "cancelled": "#dc3545",
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def save_model(self, request, obj, form, change):
        """Automatically set created_by to current user."""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Revenue)
class RevenueAdmin(admin.ModelAdmin):
    """Admin interface for tracking revenue."""

    list_display = ("description", "source", "amount", "date", "payment_method")
    list_filter = ("source", "payment_method", "date")
    search_fields = ("description", "notes")
    readonly_fields = ("created_at", "updated_at", "created_by")
    date_hierarchy = "date"

    fieldsets = (
        ("Revenue Information", {"fields": ("source", "amount", "description", "notes")}),
        ("Date and Payment", {"fields": ("date", "payment_method")}),
        ("Order Linkage", {"fields": ("related_order",)}),
        ("Metadata", {"fields": ("created_by", "created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def save_model(self, request, obj, form, change):
        """Automatically set created_by to current user."""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
