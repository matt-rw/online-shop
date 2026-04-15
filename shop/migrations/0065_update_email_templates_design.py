# Generated migration for updated email template designs

from django.db import migrations


def update_email_templates(apps, schema_editor):
    """Update order confirmation and create shipping notification templates with site-matching design."""
    EmailTemplate = apps.get_model('shop', 'EmailTemplate')

    # ============================================
    # ORDER CONFIRMATION TEMPLATE
    # ============================================
    order_html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Order Confirmed</title>
</head>
<body style="margin: 0; padding: 0; background-color: #ffffff; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; -webkit-font-smoothing: antialiased;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #ffffff;">
        <tr>
            <td align="center" style="padding: 0;">
                <table width="600" cellpadding="0" cellspacing="0" style="max-width: 600px; width: 100%;">

                    <!-- Header -->
                    <tr>
                        <td style="background-color: #000000; padding: 24px 40px; text-align: center;">
                            <span style="color: #ffffff; font-size: 11px; font-weight: 500; letter-spacing: 4px; text-transform: uppercase;">BLUEPRINT</span>
                        </td>
                    </tr>

                    <!-- Hero Section -->
                    <tr>
                        <td style="padding: 48px 40px 32px; text-align: center; border-bottom: 1px solid #e5e5e5;">
                            <p style="margin: 0 0 8px; color: #737373; font-size: 11px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase;">ORDER CONFIRMED</p>
                            <h1 style="margin: 0 0 16px; color: #000000; font-size: 28px; font-weight: 400; letter-spacing: -0.5px;">Thank you for your order</h1>
                            <p style="margin: 0; color: #525252; font-size: 15px; line-height: 1.6;">
                                Hi {customer_name}, we've received your order and are getting it ready. We'll notify you when it ships.
                            </p>
                        </td>
                    </tr>

                    <!-- Order Info -->
                    <tr>
                        <td style="padding: 32px 40px; border-bottom: 1px solid #e5e5e5;">
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td style="padding-right: 20px;">
                                        <p style="margin: 0 0 4px; color: #737373; font-size: 10px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase;">ORDER NUMBER</p>
                                        <p style="margin: 0; color: #000000; font-size: 15px; font-weight: 500;">{order_number}</p>
                                    </td>
                                    <td style="text-align: right;">
                                        <p style="margin: 0 0 4px; color: #737373; font-size: 10px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase;">ORDER DATE</p>
                                        <p style="margin: 0; color: #000000; font-size: 15px;">{order_date}</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Items Section -->
                    <tr>
                        <td style="padding: 32px 40px 24px;">
                            <p style="margin: 0 0 20px; color: #737373; font-size: 10px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase;">ITEMS ORDERED</p>
                            {items_html}
                        </td>
                    </tr>

                    <!-- Totals -->
                    <tr>
                        <td style="padding: 0 40px 32px;">
                            <table width="100%" cellpadding="0" cellspacing="0" style="border-top: 1px solid #e5e5e5; padding-top: 20px;">
                                <tr>
                                    <td style="padding: 6px 0; color: #525252; font-size: 14px;">Subtotal</td>
                                    <td style="padding: 6px 0; text-align: right; color: #000000; font-size: 14px;">{subtotal}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 6px 0; color: #525252; font-size: 14px;">Shipping</td>
                                    <td style="padding: 6px 0; text-align: right; color: #000000; font-size: 14px;">{shipping_cost}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 6px 0; color: #525252; font-size: 14px;">Tax</td>
                                    <td style="padding: 6px 0; text-align: right; color: #000000; font-size: 14px;">{tax}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 16px 0 0; color: #000000; font-size: 16px; font-weight: 600; border-top: 1px solid #000000; margin-top: 12px;">Total</td>
                                    <td style="padding: 16px 0 0; text-align: right; color: #000000; font-size: 16px; font-weight: 600; border-top: 1px solid #000000;">{total}</td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Shipping Address -->
                    <tr>
                        <td style="padding: 0 40px 40px;">
                            <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #fafafa; border: 1px solid #e5e5e5;">
                                <tr>
                                    <td style="padding: 24px;">
                                        <p style="margin: 0 0 12px; color: #737373; font-size: 10px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase;">SHIPPING TO</p>
                                        <p style="margin: 0; color: #000000; font-size: 14px; line-height: 1.7; white-space: pre-line;">{shipping_address}</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #000000; padding: 32px 40px; text-align: center;">
                            <p style="margin: 0 0 8px; color: #ffffff; font-size: 11px; font-weight: 500; letter-spacing: 3px; text-transform: uppercase;">BLUEPRINT</p>
                            <p style="margin: 0; color: #737373; font-size: 12px;">
                                Questions? Contact us at <a href="mailto:blueprint223@gmail.com" style="color: #a1a1aa;">blueprint223@gmail.com</a>
                            </p>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    order_text = """ORDER CONFIRMED

Thank you for your order, {customer_name}!

We've received your order and are getting it ready. We'll notify you when it ships.

ORDER NUMBER: {order_number}
ORDER DATE: {order_date}

ITEMS ORDERED:
{items_text}

Subtotal: {subtotal}
Shipping: {shipping_cost}
Tax: {tax}
Total: {total}

SHIPPING TO:
{shipping_address}

Questions? Contact us at blueprint223@gmail.com

BLUEPRINT"""

    # Update or create order confirmation template
    order_template, created = EmailTemplate.objects.update_or_create(
        auto_trigger='on_order',
        defaults={
            'name': 'Order Confirmation',
            'subject': 'Order Confirmed #{order_number}',
            'template_type': 'order_confirmation',
            'folder': 'transactional',
            'html_body': order_html,
            'text_body': order_text,
            'is_active': True,
        }
    )

    # ============================================
    # SHIPPING NOTIFICATION TEMPLATE
    # ============================================
    shipping_html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Your Order Has Shipped</title>
</head>
<body style="margin: 0; padding: 0; background-color: #ffffff; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; -webkit-font-smoothing: antialiased;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #ffffff;">
        <tr>
            <td align="center" style="padding: 0;">
                <table width="600" cellpadding="0" cellspacing="0" style="max-width: 600px; width: 100%;">

                    <!-- Header -->
                    <tr>
                        <td style="background-color: #000000; padding: 24px 40px; text-align: center;">
                            <span style="color: #ffffff; font-size: 11px; font-weight: 500; letter-spacing: 4px; text-transform: uppercase;">BLUEPRINT</span>
                        </td>
                    </tr>

                    <!-- Hero Section -->
                    <tr>
                        <td style="padding: 48px 40px 32px; text-align: center; border-bottom: 1px solid #e5e5e5;">
                            <p style="margin: 0 0 8px; color: #737373; font-size: 11px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase;">ORDER SHIPPED</p>
                            <h1 style="margin: 0 0 16px; color: #000000; font-size: 28px; font-weight: 400; letter-spacing: -0.5px;">Your order is on the way</h1>
                            <p style="margin: 0; color: #525252; font-size: 15px; line-height: 1.6;">
                                Great news, {customer_name}! Your order has shipped and is headed your way.
                            </p>
                        </td>
                    </tr>

                    <!-- Tracking Info -->
                    <tr>
                        <td style="padding: 32px 40px; border-bottom: 1px solid #e5e5e5;">
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td>
                                        <p style="margin: 0 0 4px; color: #737373; font-size: 10px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase;">TRACKING NUMBER</p>
                                        <p style="margin: 0 0 16px; color: #000000; font-size: 15px; font-weight: 500;">{tracking_number}</p>

                                        <p style="margin: 0 0 4px; color: #737373; font-size: 10px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase;">CARRIER</p>
                                        <p style="margin: 0; color: #000000; font-size: 15px;">{carrier}</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Track Button -->
                    <tr>
                        <td style="padding: 32px 40px; text-align: center; border-bottom: 1px solid #e5e5e5;">
                            <a href="{tracking_url}" style="display: inline-block; background-color: #000000; color: #ffffff; text-decoration: none; padding: 16px 48px; font-size: 11px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase;">TRACK YOUR ORDER</a>
                        </td>
                    </tr>

                    <!-- Order Info -->
                    <tr>
                        <td style="padding: 32px 40px;">
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td style="padding-right: 20px;">
                                        <p style="margin: 0 0 4px; color: #737373; font-size: 10px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase;">ORDER NUMBER</p>
                                        <p style="margin: 0; color: #000000; font-size: 15px; font-weight: 500;">{order_number}</p>
                                    </td>
                                    <td style="text-align: right;">
                                        <p style="margin: 0 0 4px; color: #737373; font-size: 10px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase;">ORDER DATE</p>
                                        <p style="margin: 0; color: #000000; font-size: 15px;">{order_date}</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Shipping Address -->
                    <tr>
                        <td style="padding: 0 40px 40px;">
                            <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #fafafa; border: 1px solid #e5e5e5;">
                                <tr>
                                    <td style="padding: 24px;">
                                        <p style="margin: 0 0 12px; color: #737373; font-size: 10px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase;">SHIPPING TO</p>
                                        <p style="margin: 0; color: #000000; font-size: 14px; line-height: 1.7; white-space: pre-line;">{shipping_address}</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #000000; padding: 32px 40px; text-align: center;">
                            <p style="margin: 0 0 8px; color: #ffffff; font-size: 11px; font-weight: 500; letter-spacing: 3px; text-transform: uppercase;">BLUEPRINT</p>
                            <p style="margin: 0; color: #737373; font-size: 12px;">
                                Questions? Contact us at <a href="mailto:blueprint223@gmail.com" style="color: #a1a1aa;">blueprint223@gmail.com</a>
                            </p>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    shipping_text = """YOUR ORDER HAS SHIPPED

Great news, {customer_name}! Your order is on the way.

TRACKING NUMBER: {tracking_number}
CARRIER: {carrier}

Track your order: {tracking_url}

ORDER NUMBER: {order_number}
ORDER DATE: {order_date}

SHIPPING TO:
{shipping_address}

Questions? Contact us at blueprint223@gmail.com

BLUEPRINT"""

    # Create shipping notification template (only if one doesn't exist)
    if not EmailTemplate.objects.filter(auto_trigger='on_shipping').exists():
        EmailTemplate.objects.create(
            name='Shipping Notification',
            subject='Your Order Has Shipped',
            template_type='shipping_notification',
            auto_trigger='on_shipping',
            folder='transactional',
            html_body=shipping_html,
            text_body=shipping_text,
            is_active=True,
        )


def reverse_migration(apps, schema_editor):
    # Don't delete templates on reverse - just leave them
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0064_order_email_timestamps'),
    ]

    operations = [
        migrations.RunPython(update_email_templates, reverse_migration),
    ]
