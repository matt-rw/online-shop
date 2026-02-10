from django.conf import settings
from django.contrib import admin
from django.shortcuts import render
from django.urls import include, path

from search import views as search_views
from shop import admin_views, two_factor_views, views as shop_views
from home import views as home_views


def custom_404(request, exception):
    return render(request, '404.html', status=404)


def custom_500(request):
    return render(request, '500.html', status=500)


handler404 = custom_404
handler500 = custom_500

urlpatterns = [
    path("", home_views.home_page, name="home"),
    path("django-admin/", admin.site.urls),
    path("admin/", admin_views.admin_home, name="admin_home"),
    path("admin/products/", admin_views.products_dashboard, name="admin_products"),
    path("admin/products/new/", admin_views.product_wizard, name="admin_product_wizard"),
    path(
        "admin/products/<int:product_id>/preview/",
        admin_views.product_preview,
        name="admin_product_preview",
    ),
    path("admin/categories/", admin_views.categories_dashboard, name="admin_categories"),
    path("admin/attributes/", admin_views.attributes_dashboard, name="admin_attributes"),
    path("admin/promotions/", admin_views.promotions_dashboard, name="promotions_dashboard"),
    path("admin/shipments/", admin_views.shipments_dashboard, name="admin_shipments"),
    path("admin/users/", admin_views.users_dashboard, name="admin_users"),
    path("admin/orders/", admin_views.orders_dashboard, name="admin_orders"),
    path("admin/orders/add-manual/", admin_views.add_manual_order, name="add_manual_order"),
    path(
        "admin/orders/<int:order_id>/generate-label/",
        admin_views.generate_shipping_label,
        name="generate_shipping_label",
    ),
    path(
        "admin/orders/<int:order_id>/manual-tracking/",
        admin_views.manual_tracking,
        name="manual_tracking",
    ),
    path("admin/returns/", admin_views.returns_dashboard, name="admin_returns"),
    path("admin/finance/", admin_views.finance_dashboard, name="admin_finance"),
    path("admin/messages/", admin_views.messages_dashboard, name="admin_messages"),
    path("admin/campaigns/", admin_views.campaigns_list, name="admin_campaigns_list"),
    path("admin/campaigns/create/", admin_views.campaign_create, name="admin_campaign_create"),
    path(
        "admin/campaigns/<int:campaign_id>/edit/",
        admin_views.campaign_edit,
        name="admin_campaign_edit",
    ),
    path("admin/campaigns/all/", admin_views.all_campaigns, name="admin_all_campaigns"),
    path("admin/subscribers/", admin_views.subscribers_list, name="admin_subscribers"),
    path("admin/security/", admin_views.security_dashboard, name="admin_security"),
    path("admin/homepage/", admin_views.homepage_settings, name="admin_homepage"),
    path("admin/visitors/", admin_views.visitors_dashboard, name="admin_visitors"),
    path("admin/sms/", admin_views.sms_dashboard, name="admin_sms"),
    path("admin/sms/campaigns/", admin_views.sms_campaigns, name="admin_sms_campaigns"),
    path("admin/sms/templates/", admin_views.sms_templates, name="admin_sms_templates"),
    path("admin/email/", admin_views.email_dashboard, name="admin_email"),
    path("admin/email/campaigns/", admin_views.email_campaigns, name="admin_email_campaigns"),
    path("admin/email/templates/", admin_views.email_templates, name="admin_email_templates"),
    path("admin/ab-testing/", admin_views.ab_testing_dashboard, name="admin_ab_testing"),
    path("admin/bundles/", admin_views.bundles_dashboard, name="admin_bundles"),
    path("admin/2fa/setup/", two_factor_views.two_factor_setup, name="two_factor_setup"),
    path("admin/2fa/verify/", two_factor_views.two_factor_verify, name="two_factor_verify"),
    path("admin/2fa/disable/", two_factor_views.two_factor_disable, name="two_factor_disable"),
    path("accounts/", include("allauth.urls")),  # django-allauth URLs
    path("shop/", include("shop.urls")),
    path("search/", search_views.search, name="search"),
    # Promo link tracking (short URL at root level)
    path("promo/<str:promo_code>/", shop_views.promo_redirect, name="promo_redirect"),
]


if settings.DEBUG:
    from django.conf.urls.static import static
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    # Development-only: browser reload for live development
    urlpatterns += [
        path("__reload__/", include("django_browser_reload.urls")),
    ]

    # Serve static and media files from development server
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
