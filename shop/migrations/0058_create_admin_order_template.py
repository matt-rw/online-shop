from django.db import migrations


def create_admin_order_template(apps, schema_editor):
    """Create a default admin order notification email template."""
    EmailTemplate = apps.get_model('shop', 'EmailTemplate')

    # Check if one already exists
    if EmailTemplate.objects.filter(auto_trigger='on_order_admin').exists():
        return

    html_body = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #f5f5f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f5f5; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">

                    <!-- Header -->
                    <tr>
                        <td style="background-color: #10b981; padding: 25px 40px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 20px; font-weight: 600;">NEW ORDER</h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 30px 40px;">

                            <!-- Order Summary -->
                            <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f0fdf4; border-radius: 6px; margin-bottom: 25px; border: 1px solid #bbf7d0;">
                                <tr>
                                    <td style="padding: 20px;">
                                        <table width="100%" cellpadding="0" cellspacing="0">
                                            <tr>
                                                <td>
                                                    <span style="color: #166534; font-size: 28px; font-weight: 700;">{total}</span><br>
                                                    <span style="color: #15803d; font-size: 14px;">Order {order_number}</span>
                                                </td>
                                                <td style="text-align: right;">
                                                    <span style="color: #666666; font-size: 12px;">{order_date}</span><br>
                                                    <span style="color: #666666; font-size: 12px;">{order_time}</span>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>

                            <!-- Customer Info -->
                            <h3 style="margin: 0 0 10px 0; color: #000000; font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px;">Customer</h3>
                            <p style="margin: 0 0 20px 0; color: #333333; font-size: 15px;">
                                {customer_name}<br>
                                <a href="mailto:{customer_email}" style="color: #10b981;">{customer_email}</a>
                            </p>

                            <!-- Items -->
                            <h3 style="margin: 0 0 10px 0; color: #000000; font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px;">Items</h3>
                            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 20px;">
                                <tr style="background-color: #f8f8f8;">
                                    <td style="padding: 10px 12px; font-size: 12px; color: #666666;">Item</td>
                                    <td style="padding: 10px 12px; font-size: 12px; color: #666666; text-align: center;">Qty</td>
                                    <td style="padding: 10px 12px; font-size: 12px; color: #666666; text-align: right;">Price</td>
                                </tr>
                                {items_html}
                            </table>

                            <!-- Totals -->
                            <table width="100%" cellpadding="0" cellspacing="0" style="font-size: 14px;">
                                <tr>
                                    <td style="padding: 5px 0; color: #666666;">Subtotal</td>
                                    <td style="padding: 5px 0; text-align: right;">{subtotal}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 5px 0; color: #666666;">Shipping</td>
                                    <td style="padding: 5px 0; text-align: right;">{shipping_cost}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 5px 0; color: #666666;">Tax</td>
                                    <td style="padding: 5px 0; text-align: right;">{tax}</td>
                                </tr>
                            </table>

                            <!-- Shipping Address -->
                            <h3 style="margin: 25px 0 10px 0; color: #000000; font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px;">Ship To</h3>
                            <p style="margin: 0; color: #333333; font-size: 14px; line-height: 1.5; white-space: pre-line;">{shipping_address}</p>

                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    text_body = """NEW ORDER

{total} - Order {order_number}
{order_date} {order_time}

---

CUSTOMER
{customer_name}
{customer_email}

---

ITEMS
{items_text}

Subtotal: {subtotal}
Shipping: {shipping_cost}
Tax: {tax}
Total: {total}

---

SHIP TO:
{shipping_address}"""

    EmailTemplate.objects.create(
        name="Admin Order Notification",
        template_type="order_confirmation",
        folder="notifications",
        subject="New Order: {order_number} - {total}",
        html_body=html_body,
        text_body=text_body,
        auto_trigger="on_order_admin",
        is_active=True,
    )


def remove_admin_order_template(apps, schema_editor):
    """Remove the admin order notification template."""
    EmailTemplate = apps.get_model('shop', 'EmailTemplate')
    EmailTemplate.objects.filter(
        name="Admin Order Notification",
        auto_trigger="on_order_admin"
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0057_sync_early_access_state"),
    ]

    operations = [
        migrations.RunPython(
            create_admin_order_template,
            remove_admin_order_template
        ),
    ]
