from django.urls import path

from . import views
from . import cart_views
from . import webhooks
from . import admin_views

app_name = 'shop'

urlpatterns = [
    # Email subscription
    path('subscribe/', views.subscribe, name='subscribe'),

    # SMS subscription
    path('subscribe/sms/', views.subscribe_sms, name='subscribe_sms'),

    # Cart management
    path('cart/', cart_views.cart_view, name='cart'),
    path('cart/add/', cart_views.add_to_cart_view, name='add_to_cart'),
    path('cart/update/<int:item_id>/', cart_views.update_cart_item_view, name='update_cart_item'),
    path('cart/remove/<int:item_id>/', cart_views.remove_from_cart_view, name='remove_from_cart'),

    # Checkout
    path('checkout/', cart_views.checkout_view, name='checkout'),
    path('checkout/create-session/', cart_views.create_checkout_session, name='create_checkout_session'),
    path('checkout/success/', cart_views.checkout_success_view, name='checkout_success'),

    # Webhooks
    path('webhook/stripe/', webhooks.stripe_webhook, name='stripe_webhook'),
]
