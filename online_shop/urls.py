from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from search import views as search_views
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls
from shop import admin_views, two_factor_views
# from shop import urls as shop_urls

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("admin/", admin_views.admin_home, name='admin_home'),
    path("admin/products/", admin_views.products_dashboard, name='admin_products'),
    path("admin/products/<int:product_id>/preview/", admin_views.product_preview, name='admin_product_preview'),
    path("admin/categories/", admin_views.categories_dashboard, name='admin_categories'),
    path("admin/promotions/", admin_views.discounts_dashboard, name='admin_promotions'),
    path("admin/shipments/", admin_views.shipments_dashboard, name='admin_shipments'),
    path("admin/orders/", admin_views.orders_dashboard, name='admin_orders'),
    path("admin/returns/", admin_views.returns_dashboard, name='admin_returns'),
    path("admin/campaigns/", admin_views.campaigns_list, name='admin_campaigns_list'),
    path("admin/campaigns/create/", admin_views.campaign_create, name='admin_campaign_create'),
    path("admin/campaigns/<int:campaign_id>/edit/", admin_views.campaign_edit, name='admin_campaign_edit'),
    path("admin/campaigns/all/", admin_views.all_campaigns, name='admin_all_campaigns'),
    path("admin/subscribers/", admin_views.subscribers_list, name='admin_subscribers'),
    path("admin/security/", admin_views.security_dashboard, name='admin_security'),
    path("admin/homepage/", admin_views.homepage_settings, name='admin_homepage'),
    path("admin/visitors/", admin_views.visitors_dashboard, name='admin_visitors'),
    path("admin/sms/", admin_views.sms_dashboard, name='admin_sms'),
    path("admin/sms/campaigns/", admin_views.sms_campaigns, name='admin_sms_campaigns'),
    path("admin/sms/templates/", admin_views.sms_templates, name='admin_sms_templates'),
    path("admin/email/", admin_views.email_dashboard, name='admin_email'),
    path("admin/email/campaigns/", admin_views.email_campaigns, name='admin_email_campaigns'),
    path("admin/email/templates/", admin_views.email_templates, name='admin_email_templates'),
    path("admin/2fa/setup/", two_factor_views.two_factor_setup, name='two_factor_setup'),
    path("admin/2fa/verify/", two_factor_views.two_factor_verify, name='two_factor_verify'),
    path("admin/2fa/disable/", two_factor_views.two_factor_disable, name='two_factor_disable'),
    path("wagtail-admin/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("accounts/", include("allauth.urls")),  # django-allauth URLs
    path("shop/", include('shop.urls')),
    path("search/", search_views.search, name="search"),
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
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )

urlpatterns = urlpatterns + [
    # For anything not caught by a more specific rule above, hand over to
    # Wagtail's page serving mechanism. This should be the last pattern in
    # the list:
    path("", include(wagtail_urls)),
    # Alternatively, if you want Wagtail pages to be served from a subpath
    # of your site, rather than the site root:
    #    path("pages/", include(wagtail_urls)),
]
