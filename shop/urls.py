from django.urls import path

from . import admin_views, cart_views, views, webhooks

app_name = "shop"

urlpatterns = [
    # Health checks (for monitoring)
    path("health/", views.health_check, name="health"),
    path("health/detailed/", views.health_check_detailed, name="health_detailed"),
    # Shop catalog
    path("", views.shop, name="shop"),
    # Coming soon page
    path("coming-soon/", views.coming_soon, name="coming_soon"),
    # About page
    path("about/", views.about, name="about"),
    # Privacy Policy
    path("privacy/", views.privacy, name="privacy"),
    # Terms of Service
    path("terms/", views.terms, name="terms"),
    # Product detail
    path("product/<slug:slug>/", views.product_detail, name="product_detail"),
    # Bundle detail
    path("bundle/<slug:slug>/", views.bundle_detail, name="bundle_detail"),
    # Account
    path("account/", views.account, name="account"),
    # Email subscription
    path("subscribe/", views.subscribe, name="subscribe"),
    # SMS subscription
    path("subscribe/sms/", views.subscribe_sms, name="subscribe_sms"),
    # Cart management
    path("cart/", cart_views.cart_view, name="cart"),
    path("cart/add/", cart_views.add_to_cart_view, name="add_to_cart"),
    path("cart/update/<int:item_id>/", cart_views.update_cart_item_view, name="update_cart_item"),
    path("cart/remove/<int:item_id>/", cart_views.remove_from_cart_view, name="remove_from_cart"),
    # Bundle cart management
    path("cart/add-bundle/", cart_views.add_bundle_to_cart_view, name="add_bundle_to_cart"),
    path("cart/update-bundle/<int:item_id>/", cart_views.update_bundle_item_view, name="update_bundle_item"),
    path("cart/remove-bundle/<int:item_id>/", cart_views.remove_bundle_from_cart_view, name="remove_bundle_from_cart"),
    # Checkout
    path("checkout/", cart_views.checkout_view, name="checkout"),
    path("checkout/shipping-rates/", cart_views.get_shipping_rates_view, name="get_shipping_rates"),
    path(
        "checkout/create-session/",
        cart_views.create_checkout_session,
        name="create_checkout_session",
    ),
    path("checkout/success/", cart_views.checkout_success_view, name="checkout_success"),
    # Webhooks
    path("webhook/stripe/", webhooks.stripe_webhook, name="stripe_webhook"),
    path("campaigns/process/", views.process_campaigns_webhook, name="process_campaigns_webhook"),
]
