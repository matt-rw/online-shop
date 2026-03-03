"""
Analytics, visitor tracking, bug reports, and finance admin views.
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, F, Q, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

import pytz

from shop.models import (
    Order,
    OrderItem,
    OrderStatus,
    Product,
    ProductVariant,
    SiteSettings,
)
from shop.models.analytics import PageView, VisitorSession
from shop.models.bug_report import BugReport

def bug_reports_dashboard(request):
    """
    Bug reports dashboard for submitting and managing bug reports.
    """
    # Handle AJAX requests
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        action = request.POST.get("action") or request.GET.get("action")

        # For JSON requests, parse body to get action
        if not action and request.content_type == "application/json":
            try:
                body_data = json.loads(request.body)
                action = body_data.get("action")
            except (json.JSONDecodeError, ValueError):
                pass

        if action == "submit_report":
            try:
                title = request.POST.get("title", "").strip()
                description = request.POST.get("description", "").strip()
                page_url = request.POST.get("page_url", "").strip()
                priority = request.POST.get("priority", "medium")
                screenshot_file = request.FILES.get("screenshot")

                # Optimize screenshot if provided
                optimized_screenshot = None
                if screenshot_file:
                    from django.core.files.base import ContentFile
                    from shop.utils.image_optimizer import optimize_image
                    optimized_content, filename, content_type = optimize_image(
                        screenshot_file,
                        filename=screenshot_file.name
                    )
                    optimized_screenshot = ContentFile(optimized_content, name=filename)

                if not title or not description:
                    return JsonResponse({"success": False, "error": "Title and description are required"})

                report = BugReport.objects.create(
                    title=title,
                    description=description,
                    page_url=page_url,
                    priority=priority,
                    screenshot=optimized_screenshot,
                    submitted_by=request.user,
                )

                # Send email notification only if configured
                try:
                    site_settings = SiteSettings.load()
                    admin_email = site_settings.bug_report_email

                    if admin_email:
                        from shop.utils.email_helper import send_email

                        html_body = f"""
                        <html><body>
                        <h2>New Bug Report Submitted</h2>
                        <p><strong>Title:</strong> {report.title}</p>
                        <p><strong>Priority:</strong> {report.get_priority_display()}</p>
                        <p><strong>Submitted by:</strong> {report.submitted_by.username if report.submitted_by else 'Unknown'}</p>
                        <p><strong>Page URL:</strong> {report.page_url or 'Not specified'}</p>
                        <hr>
                        <p><strong>Description:</strong></p>
                        <p>{report.description}</p>
                        <hr>
                        <p><a href="https://blueprnt.store/bp-manage/bug-reports/">View all bug reports</a></p>
                        </body></html>
                        """

                        send_email(
                            email_address=admin_email,
                            subject=f"[Bug Report] {report.title}",
                            html_body=html_body,
                        )
                except Exception as e:
                    # Don't fail if email fails
                    pass

                return JsonResponse({
                    "success": True,
                    "report_id": report.id,
                    "message": "Bug report submitted successfully!"
                })
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_status":
            try:
                data = json.loads(request.body)
                report_id = data.get("id")
                status = data.get("status")

                report = BugReport.objects.get(id=report_id)
                report.status = status

                # Set resolved_at timestamp
                if status == "resolved" and not report.resolved_at:
                    report.resolved_at = timezone.now()
                elif status != "resolved":
                    report.resolved_at = None

                report.save()
                return JsonResponse({"success": True})
            except BugReport.DoesNotExist:
                return JsonResponse({"success": False, "error": "Report not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_priority":
            try:
                data = json.loads(request.body)
                report_id = data.get("id")
                priority = data.get("priority")

                report = BugReport.objects.get(id=report_id)
                report.priority = priority
                report.save()
                return JsonResponse({"success": True})
            except BugReport.DoesNotExist:
                return JsonResponse({"success": False, "error": "Report not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "add_notes":
            try:
                data = json.loads(request.body)
                report_id = data.get("id")
                notes = data.get("notes", "")

                report = BugReport.objects.get(id=report_id)
                report.admin_notes = notes
                report.save()
                return JsonResponse({"success": True})
            except BugReport.DoesNotExist:
                return JsonResponse({"success": False, "error": "Report not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "delete_report":
            try:
                data = json.loads(request.body)
                report_id = data.get("id")
                BugReport.objects.filter(id=report_id).delete()
                return JsonResponse({"success": True})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "save_email_setting":
            try:
                data = json.loads(request.body)
                email = data.get("email", "").strip()
                site_settings = SiteSettings.load()
                site_settings.bug_report_email = email
                site_settings.save()
                return JsonResponse({"success": True})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        return JsonResponse({"success": False, "error": "Unknown action"})

    # Get filter parameters
    status_filter = request.GET.get("status", "")
    priority_filter = request.GET.get("priority", "")

    # Get bug reports
    reports = BugReport.objects.all()
    if status_filter:
        reports = reports.filter(status=status_filter)
    if priority_filter:
        reports = reports.filter(priority=priority_filter)

    # Stats
    stats = {
        "total": BugReport.objects.count(),
        "open": BugReport.objects.filter(status="open").count(),
        "in_progress": BugReport.objects.filter(status="in_progress").count(),
        "resolved": BugReport.objects.filter(status="resolved").count(),
    }

    # Get email settings
    site_settings = SiteSettings.load()

    context = {
        "reports": reports,
        "stats": stats,
        "status_filter": status_filter,
        "priority_filter": priority_filter,
        "status_choices": BugReport.STATUS_CHOICES,
        "priority_choices": BugReport.PRIORITY_CHOICES,
        "bug_report_email": site_settings.bug_report_email,
        "contact_email": site_settings.contact_email,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/bug_reports_dashboard.html", context)


def visitors_dashboard(request):
    """
    Visitor analytics dashboard showing page views, traffic sources, and device stats.
    """
    from django.db.models import Avg, Count, Q

    from shop.models import PageView, VisitorSession

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)
    last_30min = now - timedelta(minutes=30)

    # Check if we should hide bots (hidden by default for cleaner analytics)
    hide_bots = request.GET.get("hide_bots", "true") != "false"

    # Base querysets - optionally exclude bots
    if hide_bots:
        session_qs = VisitorSession.objects.exclude(device_type="bot")
        pageview_qs = PageView.objects.exclude(device_type="bot")
    else:
        session_qs = VisitorSession.objects.all()
        pageview_qs = PageView.objects.all()

    # Bot counts for display (always calculated from full dataset, not filtered)
    total_sessions_30d = VisitorSession.objects.filter(first_seen__gte=last_30d).count()
    total_pageviews_30d = PageView.objects.filter(viewed_at__gte=last_30d).count()
    bot_sessions_30d = VisitorSession.objects.filter(first_seen__gte=last_30d, device_type="bot").count()
    bot_pageviews_30d = PageView.objects.filter(viewed_at__gte=last_30d, device_type="bot").count()
    bot_sessions_today = VisitorSession.objects.filter(first_seen__gte=today_start, device_type="bot").count()

    # Calculate bot percentage
    bot_session_percent = (bot_sessions_30d / total_sessions_30d * 100) if total_sessions_30d > 0 else 0
    bot_pageview_percent = (bot_pageviews_30d / total_pageviews_30d * 100) if total_pageviews_30d > 0 else 0

    # Get top bot user agents
    top_bot_agents = (
        PageView.objects.filter(viewed_at__gte=last_30d, device_type="bot")
        .values("user_agent")
        .annotate(count=Count("id"))
        .order_by("-count")[:5]
    )

    bot_stats = {
        "total_bots_30d": bot_sessions_30d,
        "bot_pageviews_30d": bot_pageviews_30d,
        "bots_today": bot_sessions_today,
        "bot_session_percent": round(bot_session_percent, 1),
        "bot_pageview_percent": round(bot_pageview_percent, 1),
        "top_bot_agents": list(top_bot_agents),
    }

    # Quick stats
    stats = {
        "visits_today": session_qs.filter(first_seen__gte=today_start).count(),
        "page_views_today": pageview_qs.filter(viewed_at__gte=today_start).count(),
        "active_sessions": session_qs.filter(last_seen__gte=last_30min).count(),
        "visits_30d": session_qs.filter(first_seen__gte=last_30d).count(),
    }

    # Average pages per session
    avg_pages = session_qs.filter(first_seen__gte=last_30d).aggregate(
        avg=Avg("page_views")
    )
    stats["avg_pages_per_session"] = avg_pages["avg"] or 0

    # Mobile percentage
    total_visits_30d = stats["visits_30d"]
    if total_visits_30d > 0:
        mobile_visits = session_qs.filter(
            first_seen__gte=last_30d, device_type__in=["mobile", "tablet"]
        ).count()
        stats["mobile_percent"] = (mobile_visits / total_visits_30d) * 100
    else:
        stats["mobile_percent"] = 0

    # Page views for different timeframes
    def get_page_views_data(days):
        """Helper to get page views for a given number of days."""
        data = []
        for i in range(days - 1, -1, -1):
            day = now - timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            count = pageview_qs.filter(viewed_at__gte=day_start, viewed_at__lt=day_end).count()
            # Format date based on timeframe
            if days <= 7:
                date_str = day.strftime("%b %d")
            elif days <= 30:
                date_str = day.strftime("%b %d")
            else:
                date_str = day.strftime("%m/%d")
            data.append({"date": date_str, "count": count})
        return data

    page_views_7d = get_page_views_data(7)
    page_views_30d = get_page_views_data(30)
    page_views_90d = get_page_views_data(90)

    # Top countries
    top_countries = (
        session_qs.filter(first_seen__gte=last_30d)
        .exclude(country="")
        .values("country", "country_name")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    # Top cities
    top_cities = (
        session_qs.filter(first_seen__gte=last_30d)
        .exclude(city="")
        .values("city", "region", "country")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    # Location data for globe visualization
    # Get individual visitor sessions with coordinates from last 30 days
    globe_locations = []
    visitor_sessions = session_qs.filter(
        first_seen__gte=last_30d, latitude__isnull=False, longitude__isnull=False
    ).values("latitude", "longitude", "city", "country_name", "ip_address")[
        :100
    ]  # Limit to 100 most recent

    for session in visitor_sessions:
        location_label = session.get("city") or session.get("country_name") or "Unknown"
        globe_locations.append(
            {
                "lat": session["latitude"],
                "lng": session["longitude"],
                "name": location_label,
                "ip": session.get("ip_address", "Unknown"),
            }
        )

    # Top referrers
    top_referrers = (
        pageview_qs.filter(viewed_at__gte=last_30d)
        .values("referrer_domain")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    # Device breakdown
    device_stats = (
        session_qs.filter(first_seen__gte=last_30d)
        .values("device_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    import json

    device_labels = [d["device_type"].capitalize() for d in device_stats]
    device_counts = [d["count"] for d in device_stats]

    # Top pages
    top_pages = (
        pageview_qs.filter(viewed_at__gte=last_30d)
        .values("path")
        .annotate(
            views=Count("id"),
            unique_visitors=Count("session_id", distinct=True),
            avg_time=Avg("response_time_ms"),
        )
        .order_by("-views")[:10]
    )

    # Recent visitors
    recent_views = pageview_qs.all()[:20]

    # Session statistics
    from urllib.parse import urlparse
    all_sessions = session_qs.filter(first_seen__gte=last_30d)
    total_sessions = all_sessions.count()

    # Average session duration
    avg_session_duration = 0
    if total_sessions > 0:
        sessions_with_duration = all_sessions.exclude(last_seen__isnull=True)
        total_duration = 0
        for sess in sessions_with_duration:
            duration_seconds = (sess.last_seen - sess.first_seen).total_seconds()
            total_duration += duration_seconds / 60
        if sessions_with_duration.count() > 0:
            avg_session_duration = total_duration / sessions_with_duration.count()

    # Bounce rate (sessions with only 1 page view)
    bounce_rate = 0
    if total_sessions > 0:
        bounced_sessions = all_sessions.filter(page_views=1).count()
        bounce_rate = (bounced_sessions / total_sessions) * 100

    # Average pages per session
    avg_pages_per_session = 0
    if total_sessions > 0:
        total_pages = all_sessions.aggregate(total=Sum("page_views"))["total"] or 0
        avg_pages_per_session = total_pages / total_sessions

    session_stats = {
        "total_sessions": total_sessions,
        "avg_duration": avg_session_duration,
        "bounce_rate": bounce_rate,
        "avg_pages": avg_pages_per_session,
    }

    # Recent sessions with page journeys
    recent_sessions = session_qs.all().order_by("-first_seen")[:20]
    sessions_data = []

    for session in recent_sessions:
        # Get all page views for this session in chronological order
        page_views = PageView.objects.filter(session_id=session.session_id).order_by("viewed_at")

        # Build page journey
        page_journey = [{"path": pv.path, "viewed_at": pv.viewed_at} for pv in page_views]

        # Calculate session duration in minutes
        duration_minutes = 0
        if session.last_seen and session.first_seen:
            duration_seconds = (session.last_seen - session.first_seen).total_seconds()
            duration_minutes = duration_seconds / 60

        # Extract referrer domain
        referrer_domain = ""
        if session.referrer:
            try:
                parsed = urlparse(session.referrer)
                referrer_domain = parsed.netloc
            except:
                referrer_domain = "Unknown"

        sessions_data.append({
            "session_id": session.session_id,
            "first_seen": session.first_seen,
            "duration_minutes": duration_minutes,
            "page_views": session.page_views,
            "landing_page": session.landing_page,
            "device_type": session.device_type or "unknown",
            "city": session.city,
            "country": session.country_name,
            "referrer_domain": referrer_domain,
            "page_journey": page_journey,
        })

    context = {
        "stats": stats,
        "bot_stats": bot_stats,
        "hide_bots": hide_bots,
        "page_views_7d": page_views_7d,
        "page_views_30d": page_views_30d,
        "page_views_90d": page_views_90d,
        "top_countries": top_countries,
        "top_cities": top_cities,
        "top_referrers": top_referrers,
        "device_labels": json.dumps(device_labels),
        "device_counts": json.dumps(device_counts),
        "top_pages": top_pages,
        "recent_views": recent_views,
        "session_stats": session_stats,
        "recent_sessions": sessions_data,
        "globe_locations": json.dumps(globe_locations),
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/visitors.html", context)


def finance_dashboard(request):
    """
    Financial dashboard showing Stripe payments, taxes, and revenue.
    """
    import json
    from datetime import timedelta
    from decimal import Decimal

    import pytz
    import stripe
    from django.conf import settings
    from django.contrib import messages
    from django.db.models import Count, F, Q, Sum
    from django.utils import timezone

    from shop.models import Expense, ExpenseCategory, Order, OrderStatus, Shipment, ShipmentItem, ProductVariant

    # Handle Stripe connection test
    stripe_status = None
    if request.method == "POST" and request.POST.get("action") == "test_stripe":
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            # Test the connection by retrieving account info
            account = stripe.Account.retrieve()
            stripe_status = {
                "success": True,
                "account_id": account.id,
                "business_name": account.get("business_profile", {}).get("name", "N/A"),
                "country": account.country,
                "charges_enabled": account.charges_enabled,
                "payouts_enabled": account.payouts_enabled,
            }
            messages.success(request, f"Stripe connection successful! Account: {account.id}")
        except stripe.AuthenticationError:
            stripe_status = {"success": False, "error": "Invalid API key"}
            messages.error(request, "Stripe connection failed: Invalid API key")
        except stripe.APIConnectionError:
            stripe_status = {"success": False, "error": "Network error connecting to Stripe"}
            messages.error(request, "Stripe connection failed: Network error")
        except stripe.StripeError as e:
            stripe_status = {"success": False, "error": str(e)}
            messages.error(request, f"Stripe connection failed: {str(e)}")
        except Exception as e:
            stripe_status = {"success": False, "error": str(e)}
            messages.error(request, f"Stripe connection failed: {str(e)}")

    # Ensure recurring expense categories exist
    recurring_category_names = [
        "Hosting",
        "Software Subscriptions",
        "Services",
        "Platform Fees"
    ]
    for cat_name in recurring_category_names:
        ExpenseCategory.objects.get_or_create(
            name=cat_name,
            defaults={
                'description': f'Recurring {cat_name.lower()} expenses',
                'is_active': True
            }
        )

    # Handle expense addition
    if request.method == "POST" and request.POST.get("action") == "add_expense":
        try:
            category = ExpenseCategory.objects.get(id=request.POST.get("category"))
            expense = Expense.objects.create(
                category=category,
                amount=request.POST.get("amount"),
                description=request.POST.get("description"),
                notes=request.POST.get("notes", ""),
                date=request.POST.get("date"),
                vendor=request.POST.get("vendor", ""),
                payment_method=request.POST.get("payment_method", ""),
                status="paid",  # Default to paid
                created_by=request.user,
            )
            messages.success(request, f"Expense added successfully: ${expense.amount} for {expense.description}")
        except Exception as e:
            messages.error(request, f"Error adding expense: {str(e)}")

        from django.shortcuts import redirect
        return redirect("admin_finance")

    # Handle expense editing
    if request.method == "POST" and request.POST.get("action") == "edit_expense":
        try:
            expense_id = request.POST.get("expense_id")
            expense = Expense.objects.get(id=expense_id)

            category = ExpenseCategory.objects.get(id=request.POST.get("category"))
            expense.category = category
            expense.amount = request.POST.get("amount")
            expense.description = request.POST.get("description")
            expense.notes = request.POST.get("notes", "")
            expense.date = request.POST.get("date")
            expense.vendor = request.POST.get("vendor", "")
            expense.payment_method = request.POST.get("payment_method", "")
            expense.save()

            messages.success(request, f"Expense updated successfully: ${expense.amount} for {expense.description}")
        except Exception as e:
            messages.error(request, f"Error updating expense: {str(e)}")

        from django.shortcuts import redirect
        return redirect("admin_finance")

    # Get date range (last 30 days by default)
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)

    # Get all paid orders with Stripe data
    paid_orders = Order.objects.filter(
        status__in=[OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.FULFILLED]
    ).select_related("user")

    # Financial metrics
    total_revenue = paid_orders.aggregate(Sum("total"))["total__sum"] or Decimal("0")
    total_tax_collected = paid_orders.aggregate(Sum("tax"))["tax__sum"] or Decimal("0")
    total_shipping_revenue = paid_orders.aggregate(Sum("shipping"))["shipping__sum"] or Decimal(
        "0"
    )

    # Recent orders (last 30 days)
    recent_orders = paid_orders.filter(created_at__gte=start_date)
    recent_revenue = recent_orders.aggregate(Sum("total"))["total__sum"] or Decimal("0")
    recent_tax = recent_orders.aggregate(Sum("tax"))["tax__sum"] or Decimal("0")

    # Stats
    stats = {
        "total_revenue": float(total_revenue),
        "total_tax_collected": float(total_tax_collected),
        "total_shipping_revenue": float(total_shipping_revenue),
        "total_orders": paid_orders.count(),
        "recent_revenue_30d": float(recent_revenue),
        "recent_tax_30d": float(recent_tax),
        "recent_orders_30d": recent_orders.count(),
        "avg_order_value": (
            float(total_revenue / paid_orders.count()) if paid_orders.count() > 0 else 0
        ),
    }

    # Prepare transaction data for table
    transactions = []
    for order in paid_orders.order_by("-created_at")[:50]:
        transactions.append(
            {
                "id": order.id,
                "order_number": order.order_number,
                "customer": (
                    f"{order.user.first_name} {order.user.last_name}" if order.user else "Guest"
                ),
                "email": order.email or (order.user.email if order.user else ""),
                "subtotal": float(order.subtotal),
                "tax": float(order.tax),
                "shipping": float(order.shipping),
                "total": float(order.total),
                "stripe_payment_intent": order.stripe_payment_intent_id,
                "created_at": order.created_at.isoformat(),
                "status": order.status,
            }
        )

    # Daily revenue chart data (last 30 days)
    daily_data = []
    for i in range(30):
        day = end_date - timedelta(days=29 - i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        day_orders = paid_orders.filter(created_at__gte=day_start, created_at__lt=day_end)
        day_revenue = day_orders.aggregate(Sum("total"))["total__sum"] or Decimal("0")
        day_tax = day_orders.aggregate(Sum("tax"))["tax__sum"] or Decimal("0")

        daily_data.append(
            {
                "date": day.strftime("%Y-%m-%d"),
                "label": day.strftime("%b %d"),
                "revenue": float(day_revenue),
                "tax": float(day_tax),
                "order_count": day_orders.count(),
            }
        )

    # Monthly data for the chart (full calendar year)
    # Get selected year from request, default to current year
    selected_year = int(request.GET.get("year", timezone.now().year))

    # Get available years (from first order to current year)
    first_order = Order.objects.order_by("created_at").first()
    current_year = timezone.now().year
    if first_order:
        first_year = first_order.created_at.year
        available_years = list(range(first_year, current_year + 1))
    else:
        available_years = [current_year]

    monthly_data = []

    # Generate data for all 12 months of selected year
    for month_num in range(1, 13):  # January (1) to December (12)
        # Start of month
        month_start = timezone.make_aware(
            timezone.datetime(selected_year, month_num, 1, 0, 0, 0)
        )

        # End of month (start of next month)
        if month_num == 12:
            month_end = timezone.make_aware(
                timezone.datetime(selected_year + 1, 1, 1, 0, 0, 0)
            )
        else:
            month_end = timezone.make_aware(
                timezone.datetime(selected_year, month_num + 1, 1, 0, 0, 0)
            )

        # Get revenue for this month
        month_orders = paid_orders.filter(created_at__gte=month_start, created_at__lt=month_end)
        month_revenue = month_orders.aggregate(Sum("total"))["total__sum"] or Decimal("0")

        # Get expenses for this month
        month_expenses = Expense.objects.filter(
            date__gte=month_start.date(),
            date__lt=month_end.date(),
            status="paid"
        )
        month_costs = month_expenses.aggregate(Sum("amount"))["amount__sum"] or Decimal("0")

        # Calculate profit
        month_profit = month_revenue - month_costs

        monthly_data.append({
            "month": month_start.strftime("%b"),
            "month_num": month_num,
            "year": selected_year,
            "revenue": float(month_revenue),
            "costs": float(month_costs),
            "profit": float(month_profit),
        })

    # Calculate total expenses
    total_expenses = Expense.objects.filter(status="paid").aggregate(Sum("amount"))["amount__sum"] or Decimal("0")
    stats["total_expenses"] = float(total_expenses)
    stats["total_profit"] = float(total_revenue - total_expenses)

    # Calculate Stripe fees (2.9% + $0.30 per transaction)
    # Stripe charges on successful payments
    stripe_fee_percentage = Decimal("0.029")  # 2.9%
    stripe_fee_fixed = Decimal("0.30")  # $0.30 per transaction

    total_stripe_fees = Decimal("0")
    for order in paid_orders:
        fee = (order.total * stripe_fee_percentage) + stripe_fee_fixed
        total_stripe_fees += fee

    stats["total_stripe_fees"] = float(total_stripe_fees)

    # ===== INVENTORY & COGS CALCULATIONS =====

    # Cost of Goods Sold (COGS) - sum of unit_cost for all sold items
    # This comes from OrderItem.unit_cost which is set during FIFO allocation
    from shop.models import OrderItem

    cogs_result = OrderItem.objects.filter(
        order__status__in=[OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.FULFILLED],
        unit_cost__isnull=False
    ).aggregate(
        total_cogs=Sum(F('unit_cost') * F('quantity'))
    )
    total_cogs = cogs_result['total_cogs'] or Decimal("0")

    # Gross Profit = Revenue - COGS
    gross_profit = total_revenue - total_cogs

    # Net Profit = Gross Profit - Operating Expenses - Stripe Fees
    net_profit = gross_profit - total_expenses - total_stripe_fees

    stats["total_cogs"] = float(total_cogs)
    stats["gross_profit"] = float(gross_profit)
    stats["net_profit"] = float(net_profit)

    # Gross margin percentage
    if total_revenue > 0:
        stats["gross_margin_pct"] = float((gross_profit / total_revenue) * 100)
        stats["net_margin_pct"] = float((net_profit / total_revenue) * 100)
    else:
        stats["gross_margin_pct"] = 0
        stats["net_margin_pct"] = 0

    # ===== INVENTORY VALUE =====
    # Calculate current inventory value based on shipment costs
    # Only count delivered shipments, and use available_quantity (received - sold)

    inventory_items = []

    delivered_shipments = Shipment.objects.filter(status="delivered").prefetch_related(
        'items__variant__product'
    )

    # Build a map of variant costs from delivered shipments (for fallback calculations)
    variant_costs = {}
    for shipment in delivered_shipments:
        for item in shipment.items.all():
            if item.unit_cost > 0:
                variant_id = item.variant_id
                if variant_id not in variant_costs:
                    variant_costs[variant_id] = {'total_cost': Decimal("0"), 'total_qty': 0}
                variant_costs[variant_id]['total_cost'] += item.unit_cost * item.received_quantity
                variant_costs[variant_id]['total_qty'] += item.received_quantity

            # Also track inventory items for the breakdown table
            available = item.available_quantity
            if available > 0 and item.unit_cost > 0:
                item_value = available * item.unit_cost
                inventory_items.append({
                    'sku': item.variant.sku,
                    'product': item.variant.product.name,
                    'size': item.variant.size.code if item.variant.size else '',
                    'color': item.variant.color.name if item.variant.color else '',
                    'available': available,
                    'unit_cost': float(item.unit_cost),
                    'value': float(item_value),
                    'shipment': shipment.name or shipment.tracking_number,
                })

    # Calculate average cost per variant from shipments
    variant_avg_cost = {}
    for variant_id, data in variant_costs.items():
        if data['total_qty'] > 0:
            variant_avg_cost[variant_id] = data['total_cost'] / data['total_qty']

    # Also calculate total stock (even items without cost data)
    total_stock_units = ProductVariant.objects.filter(
        is_active=True
    ).aggregate(total=Sum('stock_quantity'))['total'] or 0

    # Potential revenue and inventory value using fallback costs
    potential_revenue = Decimal("0")
    inventory_value = Decimal("0")

    for variant in ProductVariant.objects.filter(is_active=True, stock_quantity__gt=0).select_related('product'):
        potential_revenue += variant.price * variant.stock_quantity

        # Get cost with fallback: shipment > variant > product base_cost
        shipment_cost = variant_avg_cost.get(variant.id, None)
        if shipment_cost:
            unit_cost = shipment_cost
        elif variant.cost and variant.cost > 0:
            unit_cost = variant.cost
        elif variant.product.base_cost and variant.product.base_cost > 0:
            unit_cost = variant.product.base_cost
        else:
            unit_cost = Decimal("0")

        inventory_value += unit_cost * variant.stock_quantity

    stats["inventory_value"] = float(inventory_value)
    stats["inventory_units"] = total_stock_units
    stats["potential_revenue"] = float(potential_revenue)
    stats["potential_profit"] = float(potential_revenue - inventory_value)

    # Sort inventory items by value (highest first)
    inventory_items.sort(key=lambda x: x['value'], reverse=True)

    # ===== PRODUCT-LEVEL PROFIT BREAKDOWN =====
    # Aggregate inventory data by product for a cleaner view
    from shop.models import Product
    from collections import defaultdict

    product_profit_data = defaultdict(lambda: {
        'stock': 0,
        'retail_value': Decimal("0"),
        'cost_value': Decimal("0"),
        'variants': []
    })

    # Get all active variants with stock
    variants_with_stock = ProductVariant.objects.filter(
        is_active=True,
        stock_quantity__gt=0
    ).select_related('product', 'size', 'color')

    # Note: variant_avg_cost is already calculated above in the inventory section

    # Aggregate by product
    for variant in variants_with_stock:
        product_name = variant.product.name
        product_id = variant.product.id
        stock = variant.stock_quantity
        retail = variant.price * stock

        # Get cost - priority: shipment data > variant cost > product base_cost
        shipment_cost = variant_avg_cost.get(variant.id, None)
        if shipment_cost:
            unit_cost = shipment_cost
            cost_source = 'shipment'
        elif variant.cost and variant.cost > 0:
            unit_cost = variant.cost
            cost_source = 'variant'
        elif variant.product.base_cost and variant.product.base_cost > 0:
            unit_cost = variant.product.base_cost
            cost_source = 'product'
        else:
            unit_cost = None
            cost_source = None

        cost = unit_cost * stock if unit_cost else Decimal("0")

        product_profit_data[product_id]['name'] = product_name
        product_profit_data[product_id]['product_id'] = product_id
        product_profit_data[product_id]['stock'] += stock
        product_profit_data[product_id]['retail_value'] += retail
        product_profit_data[product_id]['cost_value'] += cost
        product_profit_data[product_id]['base_price'] = float(variant.product.base_price)
        product_profit_data[product_id]['base_cost'] = float(variant.product.base_cost) if variant.product.base_cost else 0
        product_profit_data[product_id]['has_cost_data'] = unit_cost is not None
        product_profit_data[product_id]['variants'].append({
            'sku': variant.sku,
            'size': variant.size.code if variant.size else '',
            'color': variant.color.name if variant.color else '',
            'stock': stock,
            'price': float(variant.price),
            'cost': float(unit_cost) if unit_cost else None,
            'cost_source': cost_source,
        })

    # Convert to list and calculate profit/margin
    product_profits = []
    for product_id, data in product_profit_data.items():
        retail = data['retail_value']
        cost = data['cost_value']
        profit = retail - cost
        margin = (profit / retail * 100) if retail > 0 else 0
        has_cost = data.get('has_cost_data', cost > 0)

        product_profits.append({
            'product_id': data['product_id'],
            'name': data['name'],
            'stock': data['stock'],
            'base_price': data['base_price'],
            'base_cost': data.get('base_cost', 0),
            'retail_value': float(retail),
            'cost_value': float(cost),
            'potential_profit': float(profit),
            'margin_pct': float(margin),
            'has_cost_data': has_cost,
            'variant_count': len(data['variants']),
        })

    # Sort by potential profit (highest first)
    product_profits.sort(key=lambda x: x['potential_profit'], reverse=True)

    # Get recurring monthly expenses (like Render, etc.)
    # These are expenses with specific recurring categories
    recurring_categories = ["Hosting", "Software Subscriptions", "Services", "Platform Fees"]
    recurring_expenses = Expense.objects.filter(
        status="paid",
        category__name__in=recurring_categories
    ).select_related("category").order_by("-date")[:12]  # Last 12

    recurring_list = []
    for expense in recurring_expenses:
        recurring_list.append({
            "id": expense.id,
            "description": expense.description,
            "vendor": expense.vendor or "",
            "amount": float(expense.amount),
            "category": expense.category.name,
            "category_id": expense.category.id,
            "date": expense.date.isoformat(),
            "payment_method": expense.payment_method or "",
            "payment_method_display": expense.get_payment_method_display() if expense.payment_method else "",
            "notes": expense.notes or "",
        })

    # Monthly Stripe fees breakdown
    stripe_fees_by_month = []
    for month_num in range(1, 13):
        month_start = timezone.make_aware(
            timezone.datetime(selected_year, month_num, 1, 0, 0, 0)
        )

        if month_num == 12:
            month_end = timezone.make_aware(
                timezone.datetime(selected_year + 1, 1, 1, 0, 0, 0)
            )
        else:
            month_end = timezone.make_aware(
                timezone.datetime(selected_year, month_num + 1, 1, 0, 0, 0)
            )

        month_orders = paid_orders.filter(created_at__gte=month_start, created_at__lt=month_end)
        month_stripe_fees = Decimal("0")

        for order in month_orders:
            fee = (order.total * stripe_fee_percentage) + stripe_fee_fixed
            month_stripe_fees += fee

        stripe_fees_by_month.append({
            "month": month_start.strftime("%b"),
            "fees": float(month_stripe_fees),
            "transactions": month_orders.count(),
        })

    context = {
        "stats": stats,
        "transactions": transactions,
        "transactions_json": json.dumps(transactions),
        "daily_data_json": json.dumps(daily_data),
        "monthly_data_json": json.dumps(monthly_data),
        "expense_categories": ExpenseCategory.objects.filter(is_active=True).order_by("name"),
        "today": timezone.now().strftime("%Y-%m-%d"),
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
        "selected_year": selected_year,
        "available_years": sorted(available_years, reverse=True),  # Most recent first
        "recurring_expenses": recurring_list,
        "stripe_fees_by_month": stripe_fees_by_month,
        "stripe_fees_total_year": sum(m["fees"] for m in stripe_fees_by_month),
        "stripe_status": stripe_status,
        "inventory_items": inventory_items[:20],  # Top 20 by value
        "inventory_items_json": json.dumps(inventory_items[:50]),
        "product_profits": product_profits,
        "product_profits_json": json.dumps(product_profits),
    }

    return render(request, "admin/finance_dashboard.html", context)

def ab_testing_dashboard(request):
    """
    A/B Testing Dashboard - View and analyze performance of different variants
    across campaigns and promotions
    """
    if not request.user.is_staff:
        return redirect("home")

    from shop.models import CampaignMessage, Discount, Campaign
    from django.db.models import Sum, Avg, Q
    from collections import defaultdict
    from django.http import JsonResponse
    from django.utils import timezone
    from decimal import Decimal

    # Handle POST request to create new test
    if request.method == "POST":
        try:
            test_type = request.POST.get('test_type')

            if test_type == 'campaign_message':
                campaign_id = request.POST.get('campaign_id')
                campaign = Campaign.objects.get(id=campaign_id) if campaign_id else None

                message = CampaignMessage.objects.create(
                    campaign=campaign,
                    name=request.POST.get('message_name'),
                    message_type=request.POST.get('message_type'),
                    variant_name=request.POST.get('variant_name'),
                    test_tags=request.POST.get('test_tags', ''),
                    landing_url=request.POST.get('landing_url'),
                    utm_source=request.POST.get('utm_source'),
                    utm_medium=request.POST.get('utm_medium'),
                    utm_campaign=request.POST.get('utm_campaign'),
                    status='draft'
                )
                return JsonResponse({
                    'success': True,
                    'message': 'Campaign message created successfully',
                    'id': message.id
                })

            elif test_type == 'discount':
                discount = Discount.objects.create(
                    name=request.POST.get('discount_name'),
                    code=request.POST.get('discount_code', '').upper(),
                    discount_type=request.POST.get('discount_type'),
                    value=Decimal(request.POST.get('discount_value')),
                    variant_name=request.POST.get('variant_name'),
                    test_tags=request.POST.get('test_tags', ''),
                    landing_url=request.POST.get('landing_url'),
                    utm_source=request.POST.get('utm_source'),
                    utm_medium=request.POST.get('utm_medium'),
                    utm_campaign=request.POST.get('utm_campaign'),
                    valid_from=timezone.now(),
                    is_active=True
                )
                return JsonResponse({
                    'success': True,
                    'message': 'Discount created successfully',
                    'id': discount.id
                })

            else:
                return JsonResponse({'success': False, 'error': 'Invalid test type'})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    # Get all campaign messages with A/B test data
    campaign_messages = CampaignMessage.objects.filter(
        Q(variant_name__isnull=False) | Q(test_tags__isnull=False)
    ).exclude(
        Q(variant_name="") & Q(test_tags="")
    ).select_related("campaign", "discount").order_by("-created_at")

    # Get all discounts with A/B test data
    discounts = Discount.objects.filter(
        Q(variant_name__isnull=False) | Q(test_tags__isnull=False)
    ).exclude(
        Q(variant_name="") & Q(test_tags="")
    ).order_by("-created_at")

    # Aggregate stats by variant
    variant_stats = defaultdict(lambda: {
        "total_recipients": 0,
        "total_clicks": 0,
        "total_conversions": 0,
        "total_revenue": Decimal("0"),
        "messages": []
    })

    for msg in campaign_messages:
        if msg.variant_name:
            variant_stats[msg.variant_name]["total_recipients"] += msg.total_recipients
            variant_stats[msg.variant_name]["total_clicks"] += msg.clicks
            variant_stats[msg.variant_name]["total_conversions"] += msg.conversions
            variant_stats[msg.variant_name]["total_revenue"] += msg.revenue
            variant_stats[msg.variant_name]["messages"].append(msg)

    # Calculate aggregated metrics for each variant
    variant_comparison = []
    for variant_name, stats in variant_stats.items():
        ctr = 0
        if stats["total_recipients"] > 0:
            ctr = round((stats["total_clicks"] / stats["total_recipients"]) * 100, 2)

        conv_rate = 0
        if stats["total_clicks"] > 0:
            conv_rate = round((stats["total_conversions"] / stats["total_clicks"]) * 100, 2)

        avg_revenue = 0
        if stats["total_recipients"] > 0:
            avg_revenue = round(float(stats["total_revenue"]) / stats["total_recipients"], 2)

        variant_comparison.append({
            "variant_name": variant_name,
            "total_recipients": stats["total_recipients"],
            "total_clicks": stats["total_clicks"],
            "total_conversions": stats["total_conversions"],
            "total_revenue": stats["total_revenue"],
            "ctr": ctr,
            "conversion_rate": conv_rate,
            "avg_revenue_per_recipient": avg_revenue,
            "message_count": len(stats["messages"])
        })

    # Sort by total revenue
    variant_comparison.sort(key=lambda x: x["total_revenue"], reverse=True)

    # Aggregate stats by tag
    tag_stats = defaultdict(lambda: {
        "total_recipients": 0,
        "total_clicks": 0,
        "total_conversions": 0,
        "total_revenue": Decimal("0"),
        "messages": []
    })

    for msg in campaign_messages:
        tags = msg.get_tags_list()
        for tag in tags:
            tag_stats[tag]["total_recipients"] += msg.total_recipients
            tag_stats[tag]["total_clicks"] += msg.clicks
            tag_stats[tag]["total_conversions"] += msg.conversions
            tag_stats[tag]["total_revenue"] += msg.revenue
            tag_stats[tag]["messages"].append(msg)

    # Calculate aggregated metrics for each tag
    tag_analysis = []
    for tag_name, stats in tag_stats.items():
        ctr = 0
        if stats["total_recipients"] > 0:
            ctr = round((stats["total_clicks"] / stats["total_recipients"]) * 100, 2)

        conv_rate = 0
        if stats["total_clicks"] > 0:
            conv_rate = round((stats["total_conversions"] / stats["total_clicks"]) * 100, 2)

        avg_revenue = 0
        if stats["total_recipients"] > 0:
            avg_revenue = round(float(stats["total_revenue"]) / stats["total_recipients"], 2)

        tag_analysis.append({
            "tag_name": tag_name,
            "total_recipients": stats["total_recipients"],
            "total_clicks": stats["total_clicks"],
            "total_conversions": stats["total_conversions"],
            "total_revenue": stats["total_revenue"],
            "ctr": ctr,
            "conversion_rate": conv_rate,
            "avg_revenue_per_recipient": avg_revenue,
            "message_count": len(stats["messages"])
        })

    # Sort by conversion rate
    tag_analysis.sort(key=lambda x: x["conversion_rate"], reverse=True)

    # Prepare message data
    messages_data = []
    for msg in campaign_messages:
        messages_data.append({
            "id": msg.id,
            "name": msg.name,
            "campaign": msg.campaign.name if msg.campaign else "No Campaign",
            "message_type": msg.get_message_type_display(),
            "variant_name": msg.variant_name,
            "test_tags": msg.test_tags,
            "tracking_url": msg.get_tracking_url(),
            "total_recipients": msg.total_recipients,
            "clicks": msg.clicks,
            "conversions": msg.conversions,
            "revenue": msg.revenue,
            "ctr": msg.click_through_rate,
            "conversion_rate": msg.conversion_rate,
            "created_at": msg.created_at,
            "status": msg.get_status_display(),
        })

    # Prepare discount data
    discounts_data = []
    for discount in discounts:
        discounts_data.append({
            "id": discount.id,
            "name": discount.name,
            "code": discount.code,
            "variant_name": discount.variant_name,
            "test_tags": discount.test_tags,
            "tracking_url": discount.get_tracking_url(),
            "times_used": discount.times_used,
            "discount_type": discount.get_discount_type_display(),
            "value": discount.value,
            "created_at": discount.created_at,
        })

    # Overall stats
    total_recipients = sum(msg.total_recipients for msg in campaign_messages)
    total_clicks = sum(msg.clicks for msg in campaign_messages)
    total_conversions = sum(msg.conversions for msg in campaign_messages)
    total_revenue = sum(msg.revenue for msg in campaign_messages)

    overall_ctr = 0
    if total_recipients > 0:
        overall_ctr = round((total_clicks / total_recipients) * 100, 2)

    overall_conv_rate = 0
    if total_clicks > 0:
        overall_conv_rate = round((total_conversions / total_clicks) * 100, 2)

    # Get all campaigns for the dropdown
    campaigns = Campaign.objects.all().order_by('-created_at')

    context = {
        "campaign_messages": messages_data,
        "discounts": discounts_data,
        "variant_comparison": variant_comparison,
        "tag_analysis": tag_analysis,
        "total_recipients": total_recipients,
        "total_clicks": total_clicks,
        "total_conversions": total_conversions,
        "total_revenue": total_revenue,
        "overall_ctr": overall_ctr,
        "overall_conv_rate": overall_conv_rate,
        "active_tests_count": len(campaign_messages) + len(discounts),
        "campaigns": campaigns,
    }

    return render(request, "admin/ab_testing_dashboard.html", context)


