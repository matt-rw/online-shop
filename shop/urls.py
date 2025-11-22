from django.urls import path

from . import admin_views, cart_views, views, webhooks

app_name = "shop"

urlpatterns = [
    # Health checks (for monitoring)
    path("health/", views.health_check, name="health"),
    path("health/detailed/", views.health_check_detailed, name="health_detailed"),
    # Email subscription
    path("subscribe/", views.subscribe, name="subscribe"),
    # SMS subscription
    path("subscribe/sms/", views.subscribe_sms, name="subscribe_sms"),
    # Cart management
    path("cart/", cart_views.cart_view, name="cart"),
    path("cart/add/", cart_views.add_to_cart_view, name="add_to_cart"),
    path("cart/update/<int:item_id>/", cart_views.update_cart_item_view, name="update_cart_item"),
    path("cart/remove/<int:item_id>/", cart_views.remove_from_cart_view, name="remove_from_cart"),
    # Checkout
    path("checkout/", cart_views.checkout_view, name="checkout"),
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
