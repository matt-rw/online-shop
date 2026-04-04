from django.db import migrations


def create_default_order_template(apps, schema_editor):
    """Create a default order confirmation email template."""
    EmailTemplate = apps.get_model('shop', 'EmailTemplate')

    # Check if one already exists
    if EmailTemplate.objects.filter(auto_trigger='on_order').exists():
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
                        <td style="background-color: #000000; padding: 30px 40px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 600; letter-spacing: 2px;">BLUEPRINT</h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">

                            <!-- Thank You -->
                            <h2 style="margin: 0 0 10px 0; color: #000000; font-size: 28px; font-weight: 600;">Thank You for Your Order</h2>
                            <p style="margin: 0 0 30px 0; color: #666666; font-size: 16px; line-height: 1.6;">
                                Hi {customer_name}, we've received your order and it's being processed. You'll receive another email when it ships.
                            </p>

                            <!-- Order Info Box -->
                            <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f8f8f8; border-radius: 6px; margin-bottom: 30px;">
                                <tr>
                                    <td style="padding: 20px;">
                                        <table width="100%" cellpadding="0" cellspacing="0">
                                            <tr>
                                                <td style="padding-bottom: 10px;">
                                                    <span style="color: #999999; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">Order Number</span><br>
                                                    <span style="color: #000000; font-size: 16px; font-weight: 600;">{order_number}</span>
                                                </td>
                                                <td style="padding-bottom: 10px; text-align: right;">
                                                    <span style="color: #999999; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">Order Date</span><br>
                                                    <span style="color: #000000; font-size: 16px;">{order_date}</span>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>

                            <!-- Items Header -->
                            <h3 style="margin: 0 0 15px 0; color: #000000; font-size: 18px; font-weight: 600;">Order Details</h3>

                            <!-- Items Table -->
                            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 20px;">
                                <tr style="background-color: #f8f8f8;">
                                    <td style="padding: 12px; font-size: 12px; color: #999999; text-transform: uppercase; letter-spacing: 1px;">Item</td>
                                    <td style="padding: 12px; font-size: 12px; color: #999999; text-transform: uppercase; letter-spacing: 1px; text-align: center;">Qty</td>
                                    <td style="padding: 12px; font-size: 12px; color: #999999; text-transform: uppercase; letter-spacing: 1px; text-align: right;">Price</td>
                                </tr>
                                {items_html}
                            </table>

                            <!-- Totals -->
                            <table width="100%" cellpadding="0" cellspacing="0" style="border-top: 2px solid #f0f0f0; padding-top: 15px;">
                                <tr>
                                    <td style="padding: 8px 0; color: #666666;">Subtotal</td>
                                    <td style="padding: 8px 0; text-align: right; color: #000000;">{subtotal}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; color: #666666;">Shipping</td>
                                    <td style="padding: 8px 0; text-align: right; color: #000000;">{shipping_cost}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; color: #666666;">Tax</td>
                                    <td style="padding: 8px 0; text-align: right; color: #000000;">{tax}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 12px 0; color: #000000; font-size: 18px; font-weight: 600; border-top: 2px solid #000000;">Total</td>
                                    <td style="padding: 12px 0; text-align: right; color: #000000; font-size: 18px; font-weight: 600; border-top: 2px solid #000000;">{total}</td>
                                </tr>
                            </table>

                            <!-- Shipping Address -->
                            <table width="100%" cellpadding="0" cellspacing="0" style="margin-top: 30px; background-color: #f8f8f8; border-radius: 6px;">
                                <tr>
                                    <td style="padding: 20px;">
                                        <span style="color: #999999; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">Shipping To</span><br>
                                        <span style="color: #000000; font-size: 14px; line-height: 1.6; white-space: pre-line;">{shipping_address}</span>
                                    </td>
                                </tr>
                            </table>

                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f8f8f8; padding: 30px 40px; text-align: center; border-top: 1px solid #e5e5e5;">
                            <p style="margin: 0; color: #cccccc; font-size: 12px;">
                                Blueprint
                            </p>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    text_body = """BLUEPRINT

Thank You for Your Order

Hi {customer_name}, we've received your order and it's being processed. You'll receive another email when it ships.

Order Number: {order_number}
Order Date: {order_date}

---

ORDER DETAILS

{items_text}

---

Subtotal: {subtotal}
Shipping: {shipping_cost}
Tax: {tax}
Total: {total}

---

SHIPPING TO:
{shipping_address}

---

Blueprint"""

    EmailTemplate.objects.create(
        name="Order Confirmation",
        template_type="order_confirmation",
        folder="transactional",
        subject="Order Confirmed - {order_number}",
        html_body=html_body,
        text_body=text_body,
        auto_trigger="on_order",
        is_active=True,
    )


def remove_default_order_template(apps, schema_editor):
    """Remove the default order confirmation template."""
    EmailTemplate = apps.get_model('shop', 'EmailTemplate')
    EmailTemplate.objects.filter(
        name="Order Confirmation",
        auto_trigger="on_order"
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0053_add_missing_launch_at_field'),
    ]

    operations = [
        migrations.RunPython(
            create_default_order_template,
            remove_default_order_template
        ),
    ]
