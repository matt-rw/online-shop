# Generated migration for updated admin order template design

from django.db import migrations


def update_admin_order_template(apps, schema_editor):
    """Update admin order notification template to match site design."""
    EmailTemplate = apps.get_model('shop', 'EmailTemplate')

    admin_html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>New Order</title>
</head>
<body style="margin: 0; padding: 0; background-color: #ffffff; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; -webkit-font-smoothing: antialiased;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #ffffff;">
        <tr>
            <td align="center" style="padding: 0;">
                <table width="600" cellpadding="0" cellspacing="0" style="max-width: 600px; width: 100%;">

                    <!-- Header -->
                    <tr>
                        <td style="background-color: #000000; padding: 24px 40px;">
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td>
                                        <span style="color: #ffffff; font-size: 11px; font-weight: 500; letter-spacing: 4px; text-transform: uppercase;">BLUEPRINT</span>
                                    </td>
                                    <td style="text-align: right;">
                                        <span style="color: #22c55e; font-size: 11px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase;">NEW ORDER</span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Order Total Hero -->
                    <tr>
                        <td style="padding: 40px 40px 32px; text-align: center; border-bottom: 1px solid #e5e5e5;">
                            <p style="margin: 0 0 8px; color: #22c55e; font-size: 42px; font-weight: 700; letter-spacing: -1px;">{total}</p>
                            <p style="margin: 0 0 4px; color: #000000; font-size: 18px; font-weight: 500;">Order {order_number}</p>
                            <p style="margin: 0; color: #737373; font-size: 13px;">{order_date} at {order_time}</p>
                        </td>
                    </tr>

                    <!-- Quick Actions -->
                    <tr>
                        <td style="padding: 24px 40px; text-align: center; background-color: #fafafa; border-bottom: 1px solid #e5e5e5;">
                            <a href="{admin_url}" style="display: inline-block; background-color: #000000; color: #ffffff; text-decoration: none; padding: 12px 32px; font-size: 11px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase;">VIEW IN ADMIN</a>
                        </td>
                    </tr>

                    <!-- Customer Info -->
                    <tr>
                        <td style="padding: 32px 40px; border-bottom: 1px solid #e5e5e5;">
                            <p style="margin: 0 0 12px; color: #737373; font-size: 10px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase;">CUSTOMER</p>
                            <p style="margin: 0 0 4px; color: #000000; font-size: 16px; font-weight: 500;">{customer_name}</p>
                            <p style="margin: 0; color: #525252; font-size: 14px;">
                                <a href="mailto:{customer_email}" style="color: #525252; text-decoration: none;">{customer_email}</a>
                            </p>
                        </td>
                    </tr>

                    <!-- Items Section -->
                    <tr>
                        <td style="padding: 32px 40px 24px;">
                            <p style="margin: 0 0 16px; color: #737373; font-size: 10px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase;">ITEMS ORDERED</p>
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr style="border-bottom: 1px solid #e5e5e5;">
                                    <td style="padding: 8px 0; color: #737373; font-size: 11px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase;">Item</td>
                                    <td style="padding: 8px 0; color: #737373; font-size: 11px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; text-align: center;">Qty</td>
                                    <td style="padding: 8px 0; color: #737373; font-size: 11px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; text-align: right;">Price</td>
                                </tr>
                                {items_html}
                            </table>
                        </td>
                    </tr>

                    <!-- Totals -->
                    <tr>
                        <td style="padding: 0 40px 32px;">
                            <table width="100%" cellpadding="0" cellspacing="0" style="border-top: 1px solid #e5e5e5; padding-top: 16px;">
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
                                    <td style="padding: 16px 0 0; text-align: right; color: #22c55e; font-size: 16px; font-weight: 600; border-top: 1px solid #000000;">{total}</td>
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
                                        <p style="margin: 0 0 12px; color: #737373; font-size: 10px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase;">SHIP TO</p>
                                        <p style="margin: 0; color: #000000; font-size: 14px; line-height: 1.7; white-space: pre-line;">{shipping_address}</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #000000; padding: 24px 40px; text-align: center;">
                            <p style="margin: 0; color: #737373; font-size: 11px;">
                                Blueprint Admin Notification
                            </p>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    admin_text = """NEW ORDER - {total}

Order {order_number}
{order_date} at {order_time}

View in Admin: {admin_url}

---

CUSTOMER
{customer_name}
{customer_email}

---

ITEMS ORDERED
{items_text}

Subtotal: {subtotal}
Shipping: {shipping_cost}
Tax: {tax}
Total: {total}

---

SHIP TO
{shipping_address}

---

Blueprint Admin Notification"""

    # Update or create admin order notification template
    EmailTemplate.objects.update_or_create(
        auto_trigger='on_order_admin',
        defaults={
            'name': 'Admin Order Notification',
            'subject': 'New Order: {order_number} - {total}',
            'template_type': 'order_confirmation',
            'folder': 'notifications',
            'html_body': admin_html,
            'text_body': admin_text,
            'is_active': True,
        }
    )


def reverse_migration(apps, schema_editor):
    # Don't delete on reverse - just leave it
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0065_update_email_templates_design'),
    ]

    operations = [
        migrations.RunPython(update_admin_order_template, reverse_migration),
    ]
