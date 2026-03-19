"""
Admin views package.

This module re-exports all admin views for backwards compatibility.
The views are organized into submodules by functionality:
- home: Main admin dashboard
- orders: Order management
- products: Product, category, promotion, and bundle management
- inventory: Shipment tracking
- customers: Subscriber and user management
- messaging: SMS/email campaigns and templates
- settings: Homepage, security, and quick link settings
- analytics: Visitor analytics, bug reports, and finance
- testing: Test center and checkout testing
"""

# Re-export all views for backwards compatibility
from .home import admin_home
from .orders import (
    orders_dashboard,
    search_variants_for_order,
    add_manual_order,
    update_manual_order,
    returns_dashboard,
    get_order_shipping_rates,
    generate_shipping_label,
    manual_tracking,
    calculate_shipping_rates,
)
from .products import (
    products_dashboard,
    product_wizard,
    product_preview,
    categories_dashboard,
    promotions_dashboard,
    attributes_dashboard,
    bundles_dashboard,
)
from .inventory import shipments_dashboard
from .customers import (
    subscribers_list,
    users_dashboard,
)
from .messaging import (
    sms_dashboard,
    email_dashboard,
    sms_campaigns,
    email_campaigns,
    sms_templates,
    email_templates,
    messages_dashboard,
    campaigns_list,
    all_campaigns,
    campaign_create,
    campaign_edit,
)
from .settings import (
    homepage_settings,
    quick_links_settings,
    security_dashboard,
    warehouse_settings,
)
from .analytics import (
    visitors_dashboard,
    bug_reports_dashboard,
    finance_dashboard,
    ab_testing_dashboard,
)
from .reporting import scheduled_reports_dashboard
from .testing import (
    test_center,
    test_checkout,
)

__all__ = [
    # home
    'admin_home',
    # orders
    'orders_dashboard',
    'search_variants_for_order',
    'add_manual_order',
    'update_manual_order',
    'returns_dashboard',
    'generate_shipping_label',
    'manual_tracking',
    'calculate_shipping_rates',
    # products
    'products_dashboard',
    'product_wizard',
    'product_preview',
    'categories_dashboard',
    'promotions_dashboard',
    'attributes_dashboard',
    'bundles_dashboard',
    # inventory
    'shipments_dashboard',
    # customers
    'subscribers_list',
    'users_dashboard',
    # messaging
    'sms_dashboard',
    'email_dashboard',
    'sms_campaigns',
    'email_campaigns',
    'sms_templates',
    'email_templates',
    'messages_dashboard',
    'campaigns_list',
    'all_campaigns',
    'campaign_create',
    'campaign_edit',
    # settings
    'homepage_settings',
    'quick_links_settings',
    'security_dashboard',
    'warehouse_settings',
    # analytics
    'visitors_dashboard',
    'bug_reports_dashboard',
    'finance_dashboard',
    'ab_testing_dashboard',
    # testing
    'test_center',
    'test_checkout',
    # reporting
    'scheduled_reports_dashboard',
]
