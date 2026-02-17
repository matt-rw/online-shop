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
    path("bp-djadmin/", admin.site.urls),
    path("bp-manage/", admin_views.admin_home, name="admin_home"),
    path("bp-manage/products/", admin_views.products_dashboard, name="admin_products"),
    path("bp-manage/products/new/", admin_views.product_wizard, name="admin_product_wizard"),
    path(
        "bp-manage/products/<int:product_id>/preview/",
        admin_views.product_preview,
        name="admin_product_preview",
    ),
    path("bp-manage/categories/", admin_views.categories_dashboard, name="admin_categories"),
    path("bp-manage/attributes/", admin_views.attributes_dashboard, name="admin_attributes"),
    path("bp-manage/promotions/", admin_views.promotions_dashboard, name="promotions_dashboard"),
    path("bp-manage/shipments/", admin_views.shipments_dashboard, name="admin_shipments"),
    path("bp-manage/users/", admin_views.users_dashboard, name="admin_users"),
    path("bp-manage/orders/", admin_views.orders_dashboard, name="admin_orders"),
    path("bp-manage/orders/add-manual/", admin_views.add_manual_order, name="add_manual_order"),
    path("bp-manage/orders/search-variants/", admin_views.search_variants_for_order, name="search_variants_for_order"),
    path(
        "bp-manage/orders/<int:order_id>/generate-label/",
        admin_views.generate_shipping_label,
        name="generate_shipping_label",
    ),
    path(
        "bp-manage/orders/<int:order_id>/manual-tracking/",
        admin_views.manual_tracking,
        name="manual_tracking",
    ),
    path("bp-manage/returns/", admin_views.returns_dashboard, name="admin_returns"),
    path("bp-manage/finance/", admin_views.finance_dashboard, name="admin_finance"),
    path("bp-manage/messages/", admin_views.messages_dashboard, name="admin_messages"),
    path("bp-manage/campaigns/", admin_views.campaigns_list, name="admin_campaigns_list"),
    path("bp-manage/campaigns/create/", admin_views.campaign_create, name="admin_campaign_create"),
    path(
        "bp-manage/campaigns/<int:campaign_id>/edit/",
        admin_views.campaign_edit,
        name="admin_campaign_edit",
    ),
    path("bp-manage/campaigns/all/", admin_views.all_campaigns, name="admin_all_campaigns"),
    path("bp-manage/subscribers/", admin_views.subscribers_list, name="admin_subscribers"),
    path("bp-manage/security/", admin_views.security_dashboard, name="admin_security"),
    path("bp-manage/homepage/", admin_views.homepage_settings, name="admin_homepage"),
    path("bp-manage/quick-links/", admin_views.quick_links_settings, name="admin_quick_links"),
    path("bp-manage/bug-reports/", admin_views.bug_reports_dashboard, name="admin_bug_reports"),
    path("bp-manage/visitors/", admin_views.visitors_dashboard, name="admin_visitors"),
    path("bp-manage/sms/", admin_views.sms_dashboard, name="admin_sms"),
    path("bp-manage/sms/campaigns/", admin_views.sms_campaigns, name="admin_sms_campaigns"),
    path("bp-manage/sms/templates/", admin_views.sms_templates, name="admin_sms_templates"),
    path("bp-manage/email/", admin_views.email_dashboard, name="admin_email"),
    path("bp-manage/email/campaigns/", admin_views.email_campaigns, name="admin_email_campaigns"),
    path("bp-manage/email/templates/", admin_views.email_templates, name="admin_email_templates"),
    path("bp-manage/ab-testing/", admin_views.ab_testing_dashboard, name="admin_ab_testing"),
    path("bp-manage/bundles/", admin_views.bundles_dashboard, name="admin_bundles"),
    path("bp-manage/test-center/", admin_views.test_center, name="admin_test_center"),
    path("bp-manage/test-checkout/", admin_views.test_checkout, name="admin_test_checkout"),
    path("bp-manage/2fa/setup/", two_factor_views.two_factor_setup, name="two_factor_setup"),
    path("bp-manage/2fa/verify/", two_factor_views.two_factor_verify, name="two_factor_verify"),
    path("bp-manage/2fa/disable/", two_factor_views.two_factor_disable, name="two_factor_disable"),
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
