"""
Report generator utility for scheduled business metric reports.
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Sum
from django.utils import timezone


class ReportGenerator:
    """
    Generates business metric reports with current values and period comparisons.
    """

    # Available metrics organized by category
    METRIC_DEFINITIONS = {
        "orders": {
            "label": "Orders & Revenue",
            "metrics": {
                "total_orders": {
                    "label": "Total Orders (All Time)",
                    "description": "Total number of orders ever placed",
                },
                "orders_period": {
                    "label": "Orders This Period",
                    "description": "Orders placed during the report period",
                },
                "total_revenue": {
                    "label": "Total Revenue (All Time)",
                    "description": "Total revenue from all orders",
                    "format": "currency",
                },
                "revenue_period": {
                    "label": "Revenue This Period",
                    "description": "Revenue during the report period",
                    "format": "currency",
                },
                "avg_order_value": {
                    "label": "Average Order Value",
                    "description": "Average value per order",
                    "format": "currency",
                },
            },
        },
        "visitors": {
            "label": "Visitors & Traffic",
            "metrics": {
                "active_sessions": {
                    "label": "Active Sessions",
                    "description": "Visitors active in the last 30 minutes",
                },
                "total_visitors": {
                    "label": "Total Visitors (All Time)",
                    "description": "Total unique visitor sessions",
                },
                "visitors_period": {
                    "label": "Visitors This Period",
                    "description": "Unique visitors during the report period",
                },
                "page_views_period": {
                    "label": "Page Views This Period",
                    "description": "Total page views during the report period",
                },
                "conversion_rate": {
                    "label": "Conversion Rate",
                    "description": "Orders / Visitors percentage",
                    "format": "percent",
                },
            },
        },
        "subscribers": {
            "label": "Subscribers",
            "metrics": {
                "email_total": {
                    "label": "Total Email Subscribers",
                    "description": "All email subscribers",
                },
                "email_active": {
                    "label": "Active Email Subscribers",
                    "description": "Active (non-unsubscribed) email subscribers",
                },
                "email_new": {
                    "label": "New Email Subscribers",
                    "description": "Email subscribers added this period",
                },
                "sms_total": {
                    "label": "Total SMS Subscribers",
                    "description": "All SMS subscribers",
                },
                "sms_active": {
                    "label": "Active SMS Subscribers",
                    "description": "Active (confirmed, non-unsubscribed) SMS subscribers",
                },
                "sms_new": {
                    "label": "New SMS Subscribers",
                    "description": "SMS subscribers added this period",
                },
            },
        },
        "inventory": {
            "label": "Inventory",
            "metrics": {
                "total_products": {
                    "label": "Total Products",
                    "description": "Total number of products",
                },
                "active_products": {
                    "label": "Active Products",
                    "description": "Products currently available for sale",
                },
                "low_stock": {
                    "label": "Low Stock Items",
                    "description": "Variants with stock <= 5",
                },
                "out_of_stock": {
                    "label": "Out of Stock Items",
                    "description": "Variants with zero stock",
                },
            },
        },
        "campaigns": {
            "label": "Campaigns",
            "metrics": {
                "active_campaigns": {
                    "label": "Active Campaigns",
                    "description": "Currently active marketing campaigns",
                },
                "email_campaigns": {
                    "label": "Email Campaigns Sent",
                    "description": "Email campaigns sent this period",
                },
                "sms_campaigns": {
                    "label": "SMS Campaigns Sent",
                    "description": "SMS campaigns sent this period",
                },
            },
        },
    }

    def __init__(self, frequency="daily"):
        """
        Initialize the report generator.

        Args:
            frequency: "daily" or "weekly" - determines comparison period
        """
        self.frequency = frequency
        self.now = timezone.now()

        # Calculate period boundaries
        if frequency == "daily":
            self.period_start = self.now - timedelta(days=1)
            self.comparison_start = self.now - timedelta(days=2)
            self.comparison_end = self.period_start
        else:  # weekly
            self.period_start = self.now - timedelta(days=7)
            self.comparison_start = self.now - timedelta(days=14)
            self.comparison_end = self.period_start

    def calculate_all_metrics(self, selected_metrics=None):
        """
        Calculate all metrics (or only selected ones) with comparisons.

        Args:
            selected_metrics: List of metric IDs to include. If None, includes all.

        Returns:
            dict: Metrics organized by category with values and changes
        """
        from shop.models import (
            Campaign,
            EmailCampaign,
            EmailSubscription,
            Order,
            OrderStatus,
            PageView,
            Product,
            ProductVariant,
            SMSCampaign,
            SMSSubscription,
            VisitorSession,
        )

        results = {}

        # Get all selected metrics or default to all
        if selected_metrics is None:
            selected_metrics = []
            for category_data in self.METRIC_DEFINITIONS.values():
                selected_metrics.extend(category_data["metrics"].keys())

        # Pre-fetch common querysets
        paid_statuses = [OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.FULFILLED]

        # === ORDERS METRICS ===
        if any(m.startswith("total_orders") or m.startswith("orders_") or
               m.startswith("total_revenue") or m.startswith("revenue_") or
               m == "avg_order_value" for m in selected_metrics):

            paid_orders = Order.objects.filter(status__in=paid_statuses)
            period_orders = paid_orders.filter(created_at__gte=self.period_start)
            comparison_orders = paid_orders.filter(
                created_at__gte=self.comparison_start,
                created_at__lt=self.comparison_end
            )

            total_orders = paid_orders.count()
            orders_period = period_orders.count()
            orders_comparison = comparison_orders.count()

            total_revenue = paid_orders.aggregate(Sum("total"))["total__sum"] or Decimal("0")
            revenue_period = period_orders.aggregate(Sum("total"))["total__sum"] or Decimal("0")
            revenue_comparison = comparison_orders.aggregate(Sum("total"))["total__sum"] or Decimal("0")

            avg_order_value = float(total_revenue / total_orders) if total_orders > 0 else 0
            avg_period = float(revenue_period / orders_period) if orders_period > 0 else 0
            avg_comparison = float(revenue_comparison / orders_comparison) if orders_comparison > 0 else 0

            results["orders"] = {
                "label": "Orders & Revenue",
                "metrics": {},
            }

            if "total_orders" in selected_metrics:
                results["orders"]["metrics"]["total_orders"] = {
                    "label": "Total Orders (All Time)",
                    "value": total_orders,
                }

            if "orders_period" in selected_metrics:
                results["orders"]["metrics"]["orders_period"] = {
                    "label": f"Orders This {'Day' if self.frequency == 'daily' else 'Week'}",
                    "value": orders_period,
                    "change": self._calculate_change(orders_period, orders_comparison),
                }

            if "total_revenue" in selected_metrics:
                results["orders"]["metrics"]["total_revenue"] = {
                    "label": "Total Revenue (All Time)",
                    "value": float(total_revenue),
                    "format": "currency",
                }

            if "revenue_period" in selected_metrics:
                results["orders"]["metrics"]["revenue_period"] = {
                    "label": f"Revenue This {'Day' if self.frequency == 'daily' else 'Week'}",
                    "value": float(revenue_period),
                    "format": "currency",
                    "change": self._calculate_change(float(revenue_period), float(revenue_comparison)),
                }

            if "avg_order_value" in selected_metrics:
                results["orders"]["metrics"]["avg_order_value"] = {
                    "label": "Average Order Value",
                    "value": avg_order_value,
                    "format": "currency",
                    "change": self._calculate_change(avg_period, avg_comparison),
                }

        # === VISITORS METRICS ===
        if any(m in selected_metrics for m in
               ["active_sessions", "total_visitors", "visitors_period", "page_views_period", "conversion_rate"]):

            results["visitors"] = {
                "label": "Visitors & Traffic",
                "metrics": {},
            }

            if "active_sessions" in selected_metrics:
                active_sessions = VisitorSession.objects.filter(
                    last_seen__gte=self.now - timedelta(minutes=30)
                ).exclude(device_type="bot").count()

                results["visitors"]["metrics"]["active_sessions"] = {
                    "label": "Active Sessions",
                    "value": active_sessions,
                }

            if "total_visitors" in selected_metrics:
                total_visitors = VisitorSession.objects.exclude(device_type="bot").count()
                results["visitors"]["metrics"]["total_visitors"] = {
                    "label": "Total Visitors (All Time)",
                    "value": total_visitors,
                }

            if "visitors_period" in selected_metrics:
                visitors_period = VisitorSession.objects.filter(
                    first_seen__gte=self.period_start
                ).exclude(device_type="bot").count()

                visitors_comparison = VisitorSession.objects.filter(
                    first_seen__gte=self.comparison_start,
                    first_seen__lt=self.comparison_end
                ).exclude(device_type="bot").count()

                results["visitors"]["metrics"]["visitors_period"] = {
                    "label": f"Visitors This {'Day' if self.frequency == 'daily' else 'Week'}",
                    "value": visitors_period,
                    "change": self._calculate_change(visitors_period, visitors_comparison),
                }

            if "page_views_period" in selected_metrics:
                page_views_period = PageView.objects.filter(
                    viewed_at__gte=self.period_start
                ).exclude(device_type="bot").count()

                page_views_comparison = PageView.objects.filter(
                    viewed_at__gte=self.comparison_start,
                    viewed_at__lt=self.comparison_end
                ).exclude(device_type="bot").count()

                results["visitors"]["metrics"]["page_views_period"] = {
                    "label": f"Page Views This {'Day' if self.frequency == 'daily' else 'Week'}",
                    "value": page_views_period,
                    "change": self._calculate_change(page_views_period, page_views_comparison),
                }

            if "conversion_rate" in selected_metrics:
                # Calculate conversion rate for period
                visitors_period = VisitorSession.objects.filter(
                    first_seen__gte=self.period_start
                ).exclude(device_type="bot").count()

                orders_period = Order.objects.filter(
                    status__in=paid_statuses,
                    created_at__gte=self.period_start
                ).count()

                conversion_rate = (orders_period / visitors_period * 100) if visitors_period > 0 else 0

                # Comparison conversion rate
                visitors_comparison = VisitorSession.objects.filter(
                    first_seen__gte=self.comparison_start,
                    first_seen__lt=self.comparison_end
                ).exclude(device_type="bot").count()

                orders_comparison = Order.objects.filter(
                    status__in=paid_statuses,
                    created_at__gte=self.comparison_start,
                    created_at__lt=self.comparison_end
                ).count()

                conversion_comparison = (orders_comparison / visitors_comparison * 100) if visitors_comparison > 0 else 0

                results["visitors"]["metrics"]["conversion_rate"] = {
                    "label": "Conversion Rate",
                    "value": round(conversion_rate, 2),
                    "format": "percent",
                    "change": self._calculate_change(conversion_rate, conversion_comparison),
                }

        # === SUBSCRIBERS METRICS ===
        if any(m in selected_metrics for m in
               ["email_total", "email_active", "email_new", "sms_total", "sms_active", "sms_new"]):

            results["subscribers"] = {
                "label": "Subscribers",
                "metrics": {},
            }

            if "email_total" in selected_metrics:
                email_total = EmailSubscription.objects.count()
                results["subscribers"]["metrics"]["email_total"] = {
                    "label": "Total Email Subscribers",
                    "value": email_total,
                }

            if "email_active" in selected_metrics:
                email_active = EmailSubscription.objects.filter(is_active=True).count()
                results["subscribers"]["metrics"]["email_active"] = {
                    "label": "Active Email Subscribers",
                    "value": email_active,
                }

            if "email_new" in selected_metrics:
                email_new = EmailSubscription.objects.filter(
                    subscribed_at__gte=self.period_start
                ).count()

                email_new_comparison = EmailSubscription.objects.filter(
                    subscribed_at__gte=self.comparison_start,
                    subscribed_at__lt=self.comparison_end
                ).count()

                results["subscribers"]["metrics"]["email_new"] = {
                    "label": f"New Email Subscribers This {'Day' if self.frequency == 'daily' else 'Week'}",
                    "value": email_new,
                    "change": self._calculate_change(email_new, email_new_comparison),
                }

            if "sms_total" in selected_metrics:
                sms_total = SMSSubscription.objects.count()
                results["subscribers"]["metrics"]["sms_total"] = {
                    "label": "Total SMS Subscribers",
                    "value": sms_total,
                }

            if "sms_active" in selected_metrics:
                sms_active = SMSSubscription.objects.filter(
                    is_active=True, is_confirmed=True
                ).count()
                results["subscribers"]["metrics"]["sms_active"] = {
                    "label": "Active SMS Subscribers",
                    "value": sms_active,
                }

            if "sms_new" in selected_metrics:
                sms_new = SMSSubscription.objects.filter(
                    subscribed_at__gte=self.period_start
                ).count()

                sms_new_comparison = SMSSubscription.objects.filter(
                    subscribed_at__gte=self.comparison_start,
                    subscribed_at__lt=self.comparison_end
                ).count()

                results["subscribers"]["metrics"]["sms_new"] = {
                    "label": f"New SMS Subscribers This {'Day' if self.frequency == 'daily' else 'Week'}",
                    "value": sms_new,
                    "change": self._calculate_change(sms_new, sms_new_comparison),
                }

        # === INVENTORY METRICS ===
        if any(m in selected_metrics for m in
               ["total_products", "active_products", "low_stock", "out_of_stock"]):

            results["inventory"] = {
                "label": "Inventory",
                "metrics": {},
            }

            if "total_products" in selected_metrics:
                total_products = Product.objects.count()
                results["inventory"]["metrics"]["total_products"] = {
                    "label": "Total Products",
                    "value": total_products,
                }

            if "active_products" in selected_metrics:
                active_products = Product.objects.filter(is_active=True).count()
                results["inventory"]["metrics"]["active_products"] = {
                    "label": "Active Products",
                    "value": active_products,
                }

            if "low_stock" in selected_metrics:
                low_stock = ProductVariant.objects.filter(
                    is_active=True,
                    stock_quantity__gt=0,
                    stock_quantity__lte=5
                ).count()
                results["inventory"]["metrics"]["low_stock"] = {
                    "label": "Low Stock Items",
                    "value": low_stock,
                }

            if "out_of_stock" in selected_metrics:
                out_of_stock = ProductVariant.objects.filter(
                    is_active=True,
                    stock_quantity=0
                ).count()
                results["inventory"]["metrics"]["out_of_stock"] = {
                    "label": "Out of Stock Items",
                    "value": out_of_stock,
                }

        # === CAMPAIGNS METRICS ===
        if any(m in selected_metrics for m in
               ["active_campaigns", "email_campaigns", "sms_campaigns"]):

            results["campaigns"] = {
                "label": "Campaigns",
                "metrics": {},
            }

            if "active_campaigns" in selected_metrics:
                active_campaigns = Campaign.objects.filter(status="active").count()
                results["campaigns"]["metrics"]["active_campaigns"] = {
                    "label": "Active Campaigns",
                    "value": active_campaigns,
                }

            if "email_campaigns" in selected_metrics:
                email_campaigns_sent = EmailCampaign.objects.filter(
                    status="sent",
                    completed_at__gte=self.period_start
                ).count()

                email_campaigns_comparison = EmailCampaign.objects.filter(
                    status="sent",
                    completed_at__gte=self.comparison_start,
                    completed_at__lt=self.comparison_end
                ).count()

                results["campaigns"]["metrics"]["email_campaigns"] = {
                    "label": f"Email Campaigns Sent This {'Day' if self.frequency == 'daily' else 'Week'}",
                    "value": email_campaigns_sent,
                    "change": self._calculate_change(email_campaigns_sent, email_campaigns_comparison),
                }

            if "sms_campaigns" in selected_metrics:
                sms_campaigns_sent = SMSCampaign.objects.filter(
                    status="sent",
                    completed_at__gte=self.period_start
                ).count()

                sms_campaigns_comparison = SMSCampaign.objects.filter(
                    status="sent",
                    completed_at__gte=self.comparison_start,
                    completed_at__lt=self.comparison_end
                ).count()

                results["campaigns"]["metrics"]["sms_campaigns"] = {
                    "label": f"SMS Campaigns Sent This {'Day' if self.frequency == 'daily' else 'Week'}",
                    "value": sms_campaigns_sent,
                    "change": self._calculate_change(sms_campaigns_sent, sms_campaigns_comparison),
                }

        return results

    def _calculate_change(self, current, previous):
        """
        Calculate percentage change between current and previous values.

        Returns:
            dict: Contains percent change, direction, and formatted string
        """
        if previous == 0:
            if current == 0:
                return {"percent": 0, "direction": "none", "formatted": "No change"}
            else:
                return {"percent": 100, "direction": "up", "formatted": "+100%"}

        change = ((current - previous) / previous) * 100

        if change > 0:
            direction = "up"
            formatted = f"+{change:.1f}%"
        elif change < 0:
            direction = "down"
            formatted = f"{change:.1f}%"
        else:
            direction = "none"
            formatted = "No change"

        return {
            "percent": round(change, 1),
            "direction": direction,
            "formatted": formatted,
        }

    def format_for_email(self, metrics_data, report_name):
        """
        Format metrics data as HTML email.

        Args:
            metrics_data: Output from calculate_all_metrics()
            report_name: Name of the report

        Returns:
            str: HTML email body
        """
        import pytz
        chicago_tz = pytz.timezone("America/Chicago")
        now_chicago = timezone.now().astimezone(chicago_tz)

        period_label = "Daily" if self.frequency == "daily" else "Weekly"

        # Use table-based layout for email client compatibility
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report_name}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f5f5f5; margin: 0; padding: 20px;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto;">
        <tr>
            <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 12px 12px 0 0;">
                <h1 style="margin: 0; font-size: 24px; font-weight: 600;">{report_name}</h1>
                <p style="margin: 10px 0 0; opacity: 0.9; font-size: 14px;">{period_label} Report - {now_chicago.strftime('%B %d, %Y at %I:%M %p CT')}</p>
            </td>
        </tr>
        <tr>
            <td style="background: white; padding: 30px;">
"""

        for category_key, category_data in metrics_data.items():
            if not category_data.get("metrics"):
                continue

            html += f"""
                <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 30px;">
                    <tr>
                        <td colspan="2" style="font-size: 16px; font-weight: 600; color: #333; padding-bottom: 10px; border-bottom: 2px solid #f0f0f0;">{category_data['label']}</td>
                    </tr>
"""

            for metric_key, metric in category_data["metrics"].items():
                value = metric["value"]
                format_type = metric.get("format", "number")

                if format_type == "currency":
                    formatted_value = f"${value:,.2f}"
                elif format_type == "percent":
                    formatted_value = f"{value:.1f}%"
                else:
                    formatted_value = f"{value:,}"

                change_html = ""
                if "change" in metric:
                    change = metric["change"]
                    if change["direction"] == "up":
                        change_style = "color: #059669; background: #d1fae5;"
                    elif change["direction"] == "down":
                        change_style = "color: #dc2626; background: #fee2e2;"
                    else:
                        change_style = "color: #6b7280; background: #f3f4f6;"
                    change_html = f'<span style="font-size: 12px; margin-left: 8px; padding: 2px 6px; border-radius: 4px; {change_style}">{change["formatted"]}</span>'

                html += f"""
                    <tr>
                        <td style="color: #666; font-size: 14px; padding: 12px 0; border-bottom: 1px solid #f5f5f5;">{metric['label']}</td>
                        <td style="font-weight: 600; color: #333; font-size: 16px; padding: 12px 0; border-bottom: 1px solid #f5f5f5; text-align: right;">{formatted_value}{change_html}</td>
                    </tr>
"""

            html += """
                </table>
"""

        html += f"""
            </td>
        </tr>
        <tr>
            <td style="background: #f9fafb; padding: 20px 30px; text-align: center; color: #6b7280; font-size: 12px; border-radius: 0 0 12px 12px;">
                <p style="margin: 0 0 5px 0;">This is an automated report from Blueprint Apparel.</p>
                <p style="margin: 0;">Manage your scheduled reports at blueprnt.store/bp-manage/scheduled-reports/</p>
            </td>
        </tr>
    </table>
</body>
</html>
"""
        return html

    def format_for_sms(self, metrics_data, report_name):
        """
        Format metrics data as concise SMS text.
        Includes only key metrics to stay within SMS limits.

        Args:
            metrics_data: Output from calculate_all_metrics()
            report_name: Name of the report

        Returns:
            str: SMS message text
        """
        lines = [f"{report_name}"]

        # Priority metrics for SMS (keep it short)
        sms_priority = [
            ("orders", "orders_period", "Orders"),
            ("orders", "revenue_period", "Revenue"),
            ("visitors", "visitors_period", "Visitors"),
            ("subscribers", "email_new", "New Email"),
            ("subscribers", "sms_new", "New SMS"),
        ]

        for category_key, metric_key, short_label in sms_priority:
            if category_key in metrics_data:
                metrics = metrics_data[category_key].get("metrics", {})
                if metric_key in metrics:
                    metric = metrics[metric_key]
                    value = metric["value"]
                    format_type = metric.get("format", "number")

                    if format_type == "currency":
                        formatted = f"${value:,.0f}"
                    elif format_type == "percent":
                        formatted = f"{value:.1f}%"
                    else:
                        formatted = f"{value:,}"

                    change_str = ""
                    if "change" in metric:
                        change_str = f" ({metric['change']['formatted']})"

                    lines.append(f"{short_label}: {formatted}{change_str}")

        return "\n".join(lines)

    @classmethod
    def get_available_metrics(cls):
        """
        Get list of all available metrics with their definitions.

        Returns:
            dict: Metric definitions organized by category
        """
        return cls.METRIC_DEFINITIONS
