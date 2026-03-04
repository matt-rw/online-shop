"""
Admin home dashboard view.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.db.models import Sum
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
from shop.models.messaging import QuickMessage
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
    # Handle image upload for quick messages
    if request.method == "POST" and request.POST.get("action") == "upload_message_image":
        import base64
        import uuid
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

            # Save to media storage
            path = default_storage.save(unique_filename, ContentFile(image_bytes))
            url = default_storage.url(path)

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
    last_30d = now - timedelta(days=30)

    # Calculate orders and revenue
    total_orders = Order.objects.count()
    orders_30d = Order.objects.filter(created_at__gte=last_30d).count()
    total_revenue = Order.objects.aggregate(total=Sum("total"))["total"] or Decimal("0")
    revenue_30d = Order.objects.filter(created_at__gte=last_30d).aggregate(total=Sum("total"))["total"] or Decimal("0")

    # Calculate active sessions and visitors
    active_sessions = VisitorSession.objects.filter(last_seen__gte=now - timedelta(hours=1)).count()
    total_visitors = VisitorSession.objects.count()

    # Calculate conversion rate
    total_sessions = VisitorSession.objects.count()
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
        "orders_30d": orders_30d,
        "total_revenue": float(total_revenue),
        "revenue_30d": float(revenue_30d),
        "email_campaigns": EmailCampaign.objects.count(),
        "sms_campaigns": SMSCampaign.objects.count(),
        "active_campaigns": Campaign.objects.filter(status="active").count(),
        "total_page_views": PageView.objects.count(),
        "page_views_24h": PageView.objects.filter(viewed_at__gte=last_24h).count(),
        "total_visitors": total_visitors,
        "active_sessions": active_sessions,
        "conversion_rate": round(conversion_rate, 2),
    }

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
        "drafts": drafts,
        "load_draft": load_draft,
        "default_test_email": site_settings.default_test_email,
        "default_test_phone": site_settings.default_test_phone,
        "quick_links": quick_links,
    }

    return render(request, "admin/admin_home.html", context)
