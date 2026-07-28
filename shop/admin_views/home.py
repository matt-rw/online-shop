"""
Admin home dashboard view.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Avg, Count, F, Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

import pytz

from shop.decorators import two_factor_required
from shop.models import (
    Campaign,
    EmailCampaign,
    EmailSubscription,
    Product,
    SMSCampaign,
    SMSSubscription,
)
from shop.models.analytics import PageView, VisitorSession
from shop.models.cart import Order
from shop.models.messaging import CalendarEvent, ContactMessage, QuickMessage
from shop.models.product import ProductVariant
from shop.models.settings import QuickLink, SiteSettings

User = get_user_model()


@staff_member_required
@two_factor_required
def admin_home(request):
    """
    Central admin dashboard with quick access to all admin tools.
    Only accessible to admin/staff users.
    """
    # Calendar AJAX handlers
    if request.method == "POST" and request.POST.get("action") == "calendar_add_event":
        import json as json_mod
        try:
            data = json_mod.loads(request.body) if request.content_type == "application/json" else None
            if not data:
                data = {"date": request.POST.get("date"), "title": request.POST.get("title"), "event_type": request.POST.get("event_type", "note")}
            event = CalendarEvent.objects.create(
                date=data["date"],
                title=data["title"],
                event_type=data.get("event_type", "note"),
                created_by=request.user,
            )
            return JsonResponse({"success": True, "id": event.id})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    if request.method == "POST" and request.POST.get("action") == "calendar_delete_event":
        try:
            CalendarEvent.objects.filter(id=request.POST.get("event_id")).delete()
            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    if request.GET.get("action") == "calendar_month":
        import json as json_mod
        import calendar as cal_mod
        try:
            year = int(request.GET.get("year", now.year))
            month = int(request.GET.get("month", now.month))
            first_day, days_in_month = cal_mod.monthrange(year, month)
            m_start = datetime(year, month, 1, tzinfo=timezone.utc)
            m_end = (m_start + timedelta(days=32)).replace(day=1)

            from django.db.models.functions import TruncDate
            # Orders per day
            o_by_day = dict(
                Order.objects.filter(created_at__gte=m_start, created_at__lt=m_end)
                .annotate(day=TruncDate("created_at")).values("day")
                .annotate(count=Count("id")).values_list("day", "count")
            )
            r_by_day = dict(
                Order.objects.filter(created_at__gte=m_start, created_at__lt=m_end)
                .annotate(day=TruncDate("created_at")).values("day")
                .annotate(rev=Sum("total")).values_list("day", "rev")
            )
            # Scheduled messages
            s_msgs = list(QuickMessage.objects.filter(
                status="scheduled", scheduled_for__gte=m_start, scheduled_for__lt=m_end
            ).values("subject", "message_type", "scheduled_for"))
            # Custom events
            custom_events = list(CalendarEvent.objects.filter(
                date__gte=m_start.date(), date__lt=m_end.date()
            ).values("id", "date", "title", "event_type"))

            cal_data = {
                "year": year, "month": month,
                "monthName": m_start.strftime("%B"),
                "firstDayOfWeek": first_day,
                "daysInMonth": days_in_month,
                "today": now.day if year == now.year and month == now.month else 0,
                "days": {}, "revenue": {}, "maxRevenue": 0,
            }
            max_rev = 0
            for d in range(1, days_in_month + 1):
                d_date = m_start.date().replace(day=d)
                events = []
                oc = o_by_day.get(d_date, 0)
                dr = r_by_day.get(d_date, 0)
                if oc:
                    events.append({"type": "order", "text": f"{oc} order{'s' if oc > 1 else ''} · ${float(dr):.0f}"})
                for msg in s_msgs:
                    if msg["scheduled_for"].date() == d_date:
                        events.append({"type": "scheduled", "text": f"{msg['message_type'].upper()}: {msg['subject'][:30]}"})
                for ce in custom_events:
                    if ce["date"] == d_date:
                        events.append({"type": ce["event_type"], "text": ce["title"], "id": ce["id"]})
                if events:
                    cal_data["days"][str(d)] = events
                cal_data["revenue"][str(d)] = float(dr) if dr else 0
                if dr and float(dr) > max_rev:
                    max_rev = float(dr)
            cal_data["maxRevenue"] = max_rev
            return JsonResponse(cal_data)
        except Exception as e:
            return JsonResponse({"error": str(e)})

    # Handle image upload for quick messages
    if request.method == "POST" and request.POST.get("action") == "upload_message_image":
        import base64
        import uuid
        from django.conf import settings as django_settings
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage

        try:
            image_data = request.POST.get("image_data", "")
            filename = request.POST.get("filename", "image.jpg")

            if not image_data:
                return JsonResponse({"success": False, "error": "No image data provided"})

            # Parse base64 data
            if "," in image_data:
                header, data = image_data.split(",", 1)
            else:
                data = image_data

            # Decode base64
            image_bytes = base64.b64decode(data)

            # Generate unique filename
            ext = filename.rsplit(".", 1)[-1] if "." in filename else "jpg"
            unique_filename = f"messages/{uuid.uuid4().hex}.{ext}"

            # Use Cloudinary if configured, otherwise fall back to local storage
            if getattr(django_settings, 'CLOUDINARY_ENABLED', False):
                import cloudinary.uploader
                # Upload to Cloudinary
                result = cloudinary.uploader.upload(
                    image_bytes,
                    folder="messages",
                    public_id=uuid.uuid4().hex,
                    resource_type="image"
                )
                url = result['secure_url']
            else:
                # Save to local media storage
                path = default_storage.save(unique_filename, ContentFile(image_bytes))
                url = default_storage.url(path)
                # Make URL absolute for emails
                if url.startswith('/'):
                    url = request.build_absolute_uri(url)

            return JsonResponse({"success": True, "url": url})

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    # Handle quick send POST requests
    if request.method == "POST" and request.POST.get("action") == "quick_send":
        message_type = request.POST.get("message_type", "email")
        subject = request.POST.get("subject", "")
        content = request.POST.get("content", "")
        test_recipient = request.POST.get("test_recipient", "").strip()
        draft_id = request.POST.get("draft_id", "").strip()
        scheduled_for_str = request.POST.get("scheduled_for", "").strip()

        if not content:
            return JsonResponse({"success": False, "error": "Message content is required"})

        if message_type == "email" and not subject:
            return JsonResponse({"success": False, "error": "Subject is required for emails"})

        # Parse scheduled_for datetime if provided
        scheduled_for = None
        if scheduled_for_str:
            try:
                from datetime import datetime
                scheduled_for = datetime.fromisoformat(scheduled_for_str.replace("Z", "+00:00"))
                if timezone.is_naive(scheduled_for):
                    central_tz = pytz.timezone("America/Chicago")
                    scheduled_for = central_tz.localize(scheduled_for)
            except ValueError:
                return JsonResponse({"success": False, "error": "Invalid date/time format"})

        is_scheduled = scheduled_for and scheduled_for > timezone.now() and not test_recipient

        try:
            sent_count = 0
            failed_count = 0

            if message_type == "email":
                from shop.utils.email_helper import send_email

                if test_recipient:
                    recipients = [{"email": test_recipient, "subscription": None}]
                    recipient_count = 1
                else:
                    subscribers = EmailSubscription.objects.filter(is_active=True)
                    recipients = [{"email": sub.email, "subscription": sub} for sub in subscribers]
                    recipient_count = len(recipients)

                msg_status = "scheduled" if is_scheduled else "sending"

                if draft_id:
                    try:
                        quick_msg = QuickMessage.objects.get(id=draft_id, status="draft")
                        quick_msg.message_type = "email"
                        quick_msg.subject = subject
                        quick_msg.content = content
                        quick_msg.recipient_count = recipient_count
                        quick_msg.sent_by = request.user
                        quick_msg.status = msg_status
                        quick_msg.scheduled_for = scheduled_for
                        quick_msg.notes = "Test send" if test_recipient else ""
                        quick_msg.save()
                    except QuickMessage.DoesNotExist:
                        draft_id = None

                if not draft_id:
                    quick_msg = QuickMessage.objects.create(
                        message_type="email",
                        subject=subject,
                        content=content,
                        recipient_count=recipient_count,
                        sent_by=request.user,
                        status=msg_status,
                        scheduled_for=scheduled_for,
                        notes="Test send" if test_recipient else "",
                    )

                if is_scheduled:
                    return JsonResponse({
                        "success": True,
                        "scheduled": True,
                        "scheduled_for": scheduled_for.isoformat(),
                        "recipient_count": recipient_count,
                    })

                # Convert newlines to <br> for plain text, but preserve HTML tags like <img>
                html_content = content.replace(chr(10), '<br>')
                html_body = f"""<html><body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">{html_content}</body></html>"""

                for recipient in recipients:
                    success, _ = send_email(
                        email_address=recipient["email"],
                        subject=subject,
                        html_body=html_body,
                        subscription=recipient["subscription"],
                        quick_message=quick_msg,
                    )
                    if success:
                        sent_count += 1
                    else:
                        failed_count += 1

            else:  # SMS
                from shop.utils.twilio_helper import send_sms

                if test_recipient:
                    recipients = [{"phone": test_recipient, "subscription": None}]
                    recipient_count = 1
                else:
                    subscribers = SMSSubscription.objects.filter(is_active=True)
                    recipients = [{"phone": sub.phone_number, "subscription": sub} for sub in subscribers]
                    recipient_count = len(recipients)

                msg_status = "scheduled" if is_scheduled else "sending"

                if draft_id:
                    try:
                        quick_msg = QuickMessage.objects.get(id=draft_id, status="draft")
                        quick_msg.message_type = "sms"
                        quick_msg.subject = ""
                        quick_msg.content = content
                        quick_msg.recipient_count = recipient_count
                        quick_msg.sent_by = request.user
                        quick_msg.status = msg_status
                        quick_msg.scheduled_for = scheduled_for
                        quick_msg.notes = "Test send" if test_recipient else ""
                        quick_msg.save()
                    except QuickMessage.DoesNotExist:
                        draft_id = None

                if not draft_id:
                    quick_msg = QuickMessage.objects.create(
                        message_type="sms",
                        subject="",
                        content=content,
                        recipient_count=recipient_count,
                        sent_by=request.user,
                        status=msg_status,
                        scheduled_for=scheduled_for,
                        notes="Test send" if test_recipient else "",
                    )

                if is_scheduled:
                    return JsonResponse({
                        "success": True,
                        "scheduled": True,
                        "scheduled_for": scheduled_for.isoformat(),
                        "recipient_count": recipient_count,
                    })

                for recipient in recipients:
                    success, _ = send_sms(
                        phone_number=recipient["phone"],
                        message=content,
                        subscription=recipient["subscription"],
                        quick_message=quick_msg,
                    )
                    if success:
                        sent_count += 1
                    else:
                        failed_count += 1

            quick_msg.sent_count = sent_count
            quick_msg.failed_count = failed_count
            quick_msg.status = "sent" if failed_count == 0 else ("partial" if sent_count > 0 else "failed")
            quick_msg.sent_at = timezone.now()
            quick_msg.save()

            return JsonResponse({
                "success": True,
                "sent_count": sent_count,
                "failed_count": failed_count,
                "test_mode": bool(test_recipient),
            })

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    # Handle save draft
    if request.method == "POST" and request.POST.get("action") == "save_draft":
        message_type = request.POST.get("message_type", "email")
        subject = request.POST.get("subject", "")
        content = request.POST.get("content", "")
        draft_id = request.POST.get("draft_id")
        scheduled_for_str = request.POST.get("scheduled_for", "").strip()

        scheduled_for = None
        if scheduled_for_str:
            try:
                from datetime import datetime
                scheduled_for = datetime.fromisoformat(scheduled_for_str.replace("Z", "+00:00"))
                if timezone.is_naive(scheduled_for):
                    central_tz = pytz.timezone("America/Chicago")
                    scheduled_for = central_tz.localize(scheduled_for)
            except ValueError:
                pass

        try:
            if draft_id:
                draft = QuickMessage.objects.get(id=draft_id, status="draft")
                draft.message_type = message_type
                draft.subject = subject
                draft.content = content
                draft.scheduled_for = scheduled_for
                draft.save()
            else:
                draft = QuickMessage.objects.create(
                    message_type=message_type,
                    subject=subject,
                    content=content,
                    status="draft",
                    sent_by=request.user,
                    scheduled_for=scheduled_for,
                )
            return JsonResponse({
                "success": True,
                "draft_id": draft.id,
                "message": "Draft saved successfully",
            })
        except QuickMessage.DoesNotExist:
            return JsonResponse({"success": False, "error": "Draft not found"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    # Handle load draft
    if request.method == "POST" and request.POST.get("action") == "load_draft":
        draft_id = request.POST.get("draft_id")
        try:
            draft = QuickMessage.objects.get(id=draft_id, status="draft")
            return JsonResponse({
                "success": True,
                "draft": {
                    "id": draft.id,
                    "message_type": draft.message_type,
                    "subject": draft.subject,
                    "content": draft.content,
                    "scheduled_for": draft.scheduled_for.isoformat() if draft.scheduled_for else None,
                },
            })
        except QuickMessage.DoesNotExist:
            return JsonResponse({"success": False, "error": "Draft not found"})

    # Handle delete draft
    if request.method == "POST" and request.POST.get("action") == "delete_draft":
        draft_id = request.POST.get("draft_id")
        try:
            draft = QuickMessage.objects.get(id=draft_id, status="draft")
            draft.delete()
            return JsonResponse({"success": True, "message": "Draft deleted"})
        except QuickMessage.DoesNotExist:
            return JsonResponse({"success": False, "error": "Draft not found"})

    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_48h = now - timedelta(hours=48)
    last_30d = now - timedelta(days=30)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)

    # Calculate orders and revenue
    total_orders = Order.objects.count()
    orders_30d = Order.objects.filter(created_at__gte=last_30d).count()
    orders_today = Order.objects.filter(created_at__gte=today_start).count()
    orders_yesterday = Order.objects.filter(created_at__gte=yesterday_start, created_at__lt=today_start).count()
    total_revenue = Order.objects.aggregate(total=Sum("total"))["total"] or Decimal("0")
    last_7d = now - timedelta(days=7)
    revenue_7d = Order.objects.filter(created_at__gte=last_7d).aggregate(total=Sum("total"))["total"] or Decimal("0")
    orders_7d = Order.objects.filter(created_at__gte=last_7d).count()
    revenue_30d = Order.objects.filter(created_at__gte=last_30d).aggregate(total=Sum("total"))["total"] or Decimal("0")
    revenue_today = Order.objects.filter(created_at__gte=today_start).aggregate(total=Sum("total"))["total"] or Decimal("0")
    revenue_yesterday = Order.objects.filter(created_at__gte=yesterday_start, created_at__lt=today_start).aggregate(total=Sum("total"))["total"] or Decimal("0")

    # Calculate active sessions and visitors (exclude bots)
    _no_bots = ~models.Q(device_type="bot")
    active_sessions = VisitorSession.objects.filter(last_seen__gte=now - timedelta(hours=1)).filter(_no_bots).count()
    total_visitors = VisitorSession.objects.filter(_no_bots).count()

    # Calculate conversion rate (exclude bots)
    total_sessions = VisitorSession.objects.filter(_no_bots).count()
    conversion_rate = (total_orders / total_sessions * 100) if total_sessions > 0 else 0

    stats = {
        "total_users": User.objects.count(),
        "total_email_subs": EmailSubscription.objects.count(),
        "total_sms_subs": SMSSubscription.objects.count(),
        "active_email_subs": EmailSubscription.objects.filter(is_active=True).count(),
        "active_sms_subs": SMSSubscription.objects.filter(is_active=True).count(),
        "new_email_subs_24h": EmailSubscription.objects.filter(subscribed_at__gte=last_24h).count(),
        "new_sms_subs_24h": SMSSubscription.objects.filter(subscribed_at__gte=last_24h).count(),
        "total_products": Product.objects.exclude(slug="test-checkout-item").count(),
        "active_products": Product.objects.filter(is_active=True).exclude(slug="test-checkout-item").count(),
        "low_stock_items": ProductVariant.objects.exclude(product__slug="test-checkout-item").filter(stock_quantity__lte=10, stock_quantity__gt=0).count(),
        "out_of_stock": ProductVariant.objects.exclude(product__slug="test-checkout-item").filter(stock_quantity=0).count(),
        "total_orders": total_orders,
        "orders_7d": orders_7d,
        "orders_30d": orders_30d,
        "revenue_7d": float(revenue_7d),
        "orders_today": orders_today,
        "orders_yesterday": orders_yesterday,
        "total_revenue": float(total_revenue),
        "revenue_30d": float(revenue_30d),
        "revenue_today": float(revenue_today),
        "revenue_yesterday": float(revenue_yesterday),
        "unread_messages": ContactMessage.objects.filter(status="new").count(),
        "new_subs_today": EmailSubscription.objects.filter(subscribed_at__gte=today_start).count()
            + SMSSubscription.objects.filter(subscribed_at__gte=today_start).count(),
        # Averages
        "avg_daily_orders": round(total_orders / max((now - Order.objects.order_by('created_at').first().created_at).days, 1), 1) if total_orders > 0 else 0,
        "avg_order_value": round(float(total_revenue) / max(total_orders, 1), 2),
        "avg_daily_visitors": round(VisitorSession.objects.filter(last_seen__gte=last_30d).filter(_no_bots).count() / 30, 1),
        "email_campaigns": EmailCampaign.objects.count(),
        "sms_campaigns": SMSCampaign.objects.count(),
        "active_campaigns": Campaign.objects.filter(status="active").count(),
        "total_page_views": PageView.objects.exclude(device_type="bot").count(),
        "page_views_24h": PageView.objects.filter(viewed_at__gte=last_24h).exclude(device_type="bot").count(),
        "total_visitors": total_visitors,
        "active_sessions": active_sessions,
        "conversion_rate": round(conversion_rate, 2),
        "homepage_avg_response_ms": round(
            PageView.objects.filter(path="/", viewed_at__gte=last_24h).exclude(device_type="bot")
            .aggregate(avg=Avg("response_time_ms"))["avg"] or 0
        ),
    }

    recent_orders = Order.objects.select_related('user').order_by('-created_at')[:5]

    # Active carts with items (only carts that have items)
    from shop.models.cart import Cart, CartItem
    active_carts = Cart.objects.filter(
        is_active=True, items__isnull=False
    ).distinct().prefetch_related('items__variant__product').order_by('-updated_at')[:10]

    carts_data = []
    abandoned_cart_count = 0
    abandoned_cart_value = Decimal("0")
    for cart in active_carts:
        items = list(cart.items.select_related('variant__product').all())
        if not items:
            continue
        cart_total = sum(
            (item.variant.price if item.variant else 0) * item.quantity for item in items
        )
        is_abandoned = cart.updated_at < now - timedelta(hours=1)
        if is_abandoned:
            abandoned_cart_count += 1
            abandoned_cart_value += cart_total
        carts_data.append({
            "id": cart.id,
            "user": cart.user.email if cart.user else "Anonymous",
            "items": [{"name": item.variant.product.name if item.variant else "?", "qty": item.quantity} for item in items[:3]],
            "item_count": len(items),
            "total": float(cart_total),
            "updated": cart.updated_at.isoformat(),
            "abandoned": is_abandoned,
        })

    # Calendar data — current month orders + scheduled messages
    import calendar as cal_mod
    cal_year = now.year
    cal_month = now.month
    cal_first_day, cal_days_in_month = cal_mod.monthrange(cal_year, cal_month)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = (month_start + timedelta(days=32)).replace(day=1)

    # Orders per day this month
    from django.db.models.functions import TruncDate
    orders_by_day = dict(
        Order.objects.filter(created_at__gte=month_start, created_at__lt=next_month)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"), rev=Sum("total"))
        .values_list("day", "count")
    )

    # Revenue per day this month
    rev_by_day = dict(
        Order.objects.filter(created_at__gte=month_start, created_at__lt=next_month)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(rev=Sum("total"))
        .values_list("day", "rev")
    )

    # Scheduled messages
    scheduled_msgs = list(
        QuickMessage.objects.filter(
            status="scheduled", scheduled_for__gte=month_start, scheduled_for__lt=next_month
        ).values("subject", "message_type", "scheduled_for")
    )

    # Build calendar events
    calendar_data = {
        "year": cal_year,
        "month": cal_month,
        "monthName": now.strftime("%B"),
        "firstDayOfWeek": cal_first_day,  # 0=Monday
        "daysInMonth": cal_days_in_month,
        "today": now.day,
        "days": {},
    }
    # Custom calendar events
    custom_events = list(CalendarEvent.objects.filter(
        date__gte=month_start.date(), date__lt=next_month.date()
    ).values("id", "date", "title", "event_type"))

    for day_num in range(1, cal_days_in_month + 1):
        day_date = month_start.replace(day=day_num).date()
        events = []
        order_count = orders_by_day.get(day_date, 0)
        day_rev = rev_by_day.get(day_date, 0)
        if order_count:
            events.append({"type": "order", "text": f"{order_count} order{'s' if order_count > 1 else ''} · ${float(day_rev):.0f}"})
        for msg in scheduled_msgs:
            if msg["scheduled_for"].date() == day_date:
                events.append({"type": "scheduled", "text": f"{msg['message_type'].upper()}: {msg['subject'][:30]}"})
        for ce in custom_events:
            if ce["date"] == day_date:
                events.append({"type": ce["event_type"], "text": ce["title"], "id": ce["id"]})
        if events:
            calendar_data["days"][str(day_num)] = events

    # Revenue chart data — last 7 days + previous week for comparison
    import json as json_mod
    revenue_chart = []
    prev_week_chart = []
    for i in range(6, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        day_rev = Order.objects.filter(
            created_at__gte=day_start, created_at__lt=day_end
        ).aggregate(total=Sum("total"))["total"] or Decimal("0")
        revenue_chart.append({
            "label": day_start.strftime("%a"),
            "value": float(day_rev),
        })
        # Previous week same day
        prev_start = day_start - timedelta(days=7)
        prev_end = prev_start + timedelta(days=1)
        prev_rev = Order.objects.filter(
            created_at__gte=prev_start, created_at__lt=prev_end
        ).aggregate(total=Sum("total"))["total"] or Decimal("0")
        prev_week_chart.append(float(prev_rev))

    # Product performance
    from shop.models.cart import OrderItem
    product_perf = []
    for prod in Product.objects.filter(is_active=True).exclude(slug__startswith="test-"):
        total_sold = OrderItem.objects.filter(
            variant__product=prod
        ).aggregate(units=Sum('quantity'))['units'] or 0
        total_stock = sum(v.stock_quantity for v in prod.variants.filter(is_active=True))
        # Weekly avg (based on product age)
        days_active = max((now - prod.created_at).days, 1) if prod.created_at else 1
        weeks_active = max(days_active / 7, 1)
        avg_per_week = round(total_sold / weeks_active, 1)
        # Profit margin
        margin = 0
        if prod.base_price and prod.base_cost and prod.base_price > 0:
            margin = round(float((prod.base_price - prod.base_cost) / prod.base_price * 100), 0)
        product_perf.append({
            "name": prod.name,
            "sold": total_sold,
            "stock": total_stock,
            "margin": margin,
            "avg_week": avg_per_week,
            "price": float(prod.base_price),
        })
    product_perf.sort(key=lambda x: x["sold"], reverse=True)

    # Subscriber sparkline — last 7 days
    sub_sparkline = []
    for i in range(6, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        count = EmailSubscription.objects.filter(
            subscribed_at__gte=day_start, subscribed_at__lt=day_end
        ).count()
        sub_sparkline.append(count)

    # Conversion funnel
    from shop.models.cart import Cart
    funnel_visitors = VisitorSession.objects.filter(last_seen__gte=last_30d).filter(_no_bots).count() or 1
    funnel_carts = Cart.objects.filter(created_at__gte=last_30d).count()
    funnel_orders = orders_30d
    funnel_data = {
        "visitors": funnel_visitors,
        "carts": funnel_carts,
        "cart_rate": round(funnel_carts / funnel_visitors * 100, 1) if funnel_visitors else 0,
        "orders": funnel_orders,
        "order_rate": round(funnel_orders / funnel_visitors * 100, 1) if funnel_visitors else 0,
    }

    # Last order time
    last_order = Order.objects.order_by('-created_at').first()
    last_order_time = last_order.created_at.isoformat() if last_order else None

    # Calendar revenue heatmap data
    cal_rev_by_day = {}
    max_day_rev = Decimal("0")
    for day_num in range(1, cal_days_in_month + 1):
        day_date = month_start.replace(day=day_num).date()
        r = rev_by_day.get(day_date, Decimal("0"))
        cal_rev_by_day[str(day_num)] = float(r)
        if r > max_day_rev:
            max_day_rev = r
    calendar_data["revenue"] = cal_rev_by_day
    calendar_data["maxRevenue"] = float(max_day_rev)

    # Activity feed — recent events (orders, signups, messages, page views)
    activity_feed = []
    for order in Order.objects.order_by('-created_at')[:8]:
        activity_feed.append({
            "type": "order",
            "text": f"New order {order.order_number} — ${order.total:.2f}",
            "time": order.created_at.isoformat(),
        })
    for sub in EmailSubscription.objects.order_by('-subscribed_at')[:5]:
        activity_feed.append({
            "type": "signup",
            "text": f"New subscriber: {sub.email}",
            "time": sub.subscribed_at.isoformat(),
        })
    for msg in ContactMessage.objects.filter(status="new").order_by('-created_at')[:3]:
        activity_feed.append({
            "type": "message",
            "text": f"Message from {msg.name}: {msg.subject[:40]}",
            "time": msg.created_at.isoformat(),
        })
    for pv in PageView.objects.filter(viewed_at__gte=last_24h).exclude(path__startswith="/bp-manage").exclude(device_type="bot").order_by('-viewed_at')[:5]:
        activity_feed.append({
            "type": "view",
            "text": f"Page view: {pv.path}",
            "time": pv.viewed_at.isoformat(),
        })
    activity_feed.sort(key=lambda x: x["time"], reverse=True)
    activity_feed = activity_feed[:15]

    # Visitor locations — active now + last 7 days (no bots)
    last_7d = now - timedelta(days=7)
    active_visitor_sessions = list(
        VisitorSession.objects.filter(
            country__isnull=False, last_seen__gte=now - timedelta(hours=1)
        ).exclude(country="").exclude(device_type="bot").values(
            'country', 'country_name', 'city', 'first_seen', 'last_seen'
        ).order_by('-last_seen')[:15]
    )
    recent_visitor_sessions = list(
        VisitorSession.objects.filter(
            country__isnull=False, last_seen__gte=last_7d
        ).exclude(country="").exclude(device_type="bot").values(
            'country', 'country_name', 'city', 'first_seen', 'last_seen'
        ).order_by('-last_seen')[:30]
    )
    # Convert datetimes for JSON
    def _serialize_visitors(sessions):
        result = []
        for v in sessions:
            result.append({
                "country": v["country"],
                "country_name": v["country_name"],
                "city": v["city"],
                "duration_mins": round((v["last_seen"] - v["first_seen"]).total_seconds() / 60),
                "last_seen": v["last_seen"].isoformat(),
            })
        return result

    active_visitors_data = _serialize_visitors(active_visitor_sessions)
    recent_visitors_data = _serialize_visitors(recent_visitor_sessions)

    drafts = QuickMessage.objects.filter(status="draft").order_by("-updated_at")[:5]

    load_draft_id = request.GET.get("load_draft")
    load_draft = None
    if load_draft_id:
        try:
            load_draft = QuickMessage.objects.get(id=load_draft_id, status="draft")
        except QuickMessage.DoesNotExist:
            pass

    site_settings = SiteSettings.load()
    quick_links = QuickLink.objects.filter(is_active=True).order_by('display_order', 'name')

    context = {
        "stats": stats,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
        "recent_orders": recent_orders,
        "revenue_chart_json": json_mod.dumps(revenue_chart),
        "prev_week_chart_json": json_mod.dumps(prev_week_chart),
        "activity_feed_json": json_mod.dumps(activity_feed),
        "active_visitors_json": json_mod.dumps(active_visitors_data),
        "recent_visitors_json": json_mod.dumps(recent_visitors_data),
        "calendar_json": json_mod.dumps(calendar_data),
        "carts_json": json_mod.dumps(carts_data),
        "active_cart_count": len(carts_data),
        "abandoned_cart_count": abandoned_cart_count,
        "abandoned_cart_value": float(abandoned_cart_value),
        "product_perf_json": json_mod.dumps(product_perf),
        "sub_sparkline_json": json_mod.dumps(sub_sparkline),
        "funnel_json": json_mod.dumps(funnel_data),
        "last_order_time": last_order_time,
        "drafts": drafts,
        "load_draft": load_draft,
        "default_test_email": site_settings.default_test_email,
        "default_test_phone": site_settings.default_test_phone,
        "quick_links": quick_links,
    }

    return render(request, "admin/admin_home.html", context)
