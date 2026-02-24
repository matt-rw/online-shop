import base64
import csv
import io
import json
import logging
import uuid
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

import pytz

from .decorators import two_factor_required
from .models import (
    Campaign,
    CampaignMessage,
    ConnectionLog,
    EmailCampaign,
    EmailLog,
    EmailSubscription,
    EmailTemplate,
    Product,
    SiteSettings,
    SMSCampaign,
    SMSLog,
    SMSSubscription,
    SMSTemplate,
)
from .models.settings import QuickLink
from .models.bug_report import BugReport
from .models.analytics import PageView, VisitorSession

User = get_user_model()


@staff_member_required
@two_factor_required
def admin_home(request):
    """
    Central admin dashboard with quick access to all admin tools.
    Only accessible to admin/staff users.
    """
    from django.http import JsonResponse

    from .models.analytics import PageView, VisitorSession
    from .models.cart import Order
    from .models.messaging import QuickMessage
    from .models.product import ProductVariant

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
                # Parse ISO format datetime from form (user's local time is Central)
                scheduled_for = datetime.fromisoformat(scheduled_for_str.replace("Z", "+00:00"))
                if timezone.is_naive(scheduled_for):
                    # Interpret as Central Time (user's timezone)
                    central_tz = pytz.timezone("America/Chicago")
                    scheduled_for = central_tz.localize(scheduled_for)
            except ValueError:
                return JsonResponse({"success": False, "error": "Invalid date/time format"})

        # Check if this is a scheduled message (future time, not a test)
        is_scheduled = scheduled_for and scheduled_for > timezone.now() and not test_recipient

        try:
            sent_count = 0
            failed_count = 0

            if message_type == "email":
                from .utils.email_helper import send_email

                # Determine recipients
                if test_recipient:
                    # Test mode - send to single recipient
                    recipients = [{"email": test_recipient, "subscription": None}]
                    recipient_count = 1
                else:
                    # Production mode - send to all active subscribers
                    subscribers = EmailSubscription.objects.filter(is_active=True)
                    recipients = [{"email": sub.email, "subscription": sub} for sub in subscribers]
                    recipient_count = len(recipients)

                # Determine status based on scheduling
                msg_status = "scheduled" if is_scheduled else "sending"

                # Use existing draft or create new QuickMessage record
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
                        draft_id = None  # Fall through to create new

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

                # If scheduled for later, return without sending
                if is_scheduled:
                    return JsonResponse({
                        "success": True,
                        "scheduled": True,
                        "scheduled_for": scheduled_for.isoformat(),
                        "recipient_count": recipient_count,
                    })

                # Wrap content in basic HTML
                html_body = f"<html><body><p>{content.replace(chr(10), '<br>')}</p></body></html>"

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
                from .utils.twilio_helper import send_sms

                # Determine recipients
                if test_recipient:
                    # Test mode - send to single recipient
                    recipients = [{"phone": test_recipient, "subscription": None}]
                    recipient_count = 1
                else:
                    # Production mode - send to all active subscribers
                    subscribers = SMSSubscription.objects.filter(is_active=True)
                    recipients = [{"phone": sub.phone_number, "subscription": sub} for sub in subscribers]
                    recipient_count = len(recipients)

                # Determine status based on scheduling
                msg_status = "scheduled" if is_scheduled else "sending"

                # Use existing draft or create new QuickMessage record
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
                        draft_id = None  # Fall through to create new

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

                # If scheduled for later, return without sending
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

            # Update QuickMessage with results
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

        # Parse scheduled_for if provided
        scheduled_for = None
        if scheduled_for_str:
            try:
                from datetime import datetime
                scheduled_for = datetime.fromisoformat(scheduled_for_str.replace("Z", "+00:00"))
                if timezone.is_naive(scheduled_for):
                    # Interpret as Central Time (user's timezone)
                    central_tz = pytz.timezone("America/Chicago")
                    scheduled_for = central_tz.localize(scheduled_for)
            except ValueError:
                pass  # Ignore invalid dates for drafts

        try:
            if draft_id:
                # Update existing draft
                draft = QuickMessage.objects.get(id=draft_id, status="draft")
                draft.message_type = message_type
                draft.subject = subject
                draft.content = content
                draft.scheduled_for = scheduled_for
                draft.save()
            else:
                # Create new draft
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

    from decimal import Decimal

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

    # Quick stats - comprehensive metrics from all dashboards
    stats = {
        # Users & Subscribers
        "total_users": User.objects.count(),
        "total_email_subs": EmailSubscription.objects.count(),
        "total_sms_subs": SMSSubscription.objects.count(),
        "active_email_subs": EmailSubscription.objects.filter(is_active=True).count(),
        "active_sms_subs": SMSSubscription.objects.filter(is_active=True).count(),
        "new_email_subs_24h": EmailSubscription.objects.filter(subscribed_at__gte=last_24h).count(),
        "new_sms_subs_24h": SMSSubscription.objects.filter(subscribed_at__gte=last_24h).count(),

        # Products & Inventory (exclude test products)
        "total_products": Product.objects.exclude(slug="test-checkout-item").count(),
        "active_products": Product.objects.filter(is_active=True).exclude(slug="test-checkout-item").count(),
        "low_stock_items": ProductVariant.objects.exclude(product__slug="test-checkout-item").filter(stock_quantity__lte=10, stock_quantity__gt=0).count(),
        "out_of_stock": ProductVariant.objects.exclude(product__slug="test-checkout-item").filter(stock_quantity=0).count(),

        # Orders & Sales
        "total_orders": total_orders,
        "orders_30d": orders_30d,
        "total_revenue": float(total_revenue),
        "revenue_30d": float(revenue_30d),

        # Marketing & Campaigns
        "email_campaigns": EmailCampaign.objects.count(),
        "sms_campaigns": SMSCampaign.objects.count(),
        "active_campaigns": Campaign.objects.filter(status="active").count(),

        # Analytics & Traffic
        "total_page_views": PageView.objects.count(),
        "page_views_24h": PageView.objects.filter(viewed_at__gte=last_24h).count(),
        "total_visitors": total_visitors,
        "active_sessions": active_sessions,
        "conversion_rate": round(conversion_rate, 2),
    }

    # Get drafts for quick messages
    drafts = QuickMessage.objects.filter(status="draft").order_by("-updated_at")[:5]

    # Check if loading a specific draft from query param
    load_draft_id = request.GET.get("load_draft")
    load_draft = None
    if load_draft_id:
        try:
            load_draft = QuickMessage.objects.get(id=load_draft_id, status="draft")
        except QuickMessage.DoesNotExist:
            pass

    # Get test defaults from site settings
    from .models.settings import SiteSettings
    site_settings = SiteSettings.load()

    # Get active quick links grouped by category
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


@staff_member_required
def subscribers_list(request):
    """
    Display list of email subscribers and registered users.
    Only accessible to admin/staff users.
    Handles CSV upload for bulk subscriber and user import.
    """
    # Handle Delete Actions
    if request.method == "POST" and request.POST.get("delete_action"):
        delete_action = request.POST.get("delete_action")
        delete_id = request.POST.get("delete_id")

        try:
            if delete_action == "subscriber":
                subscriber = EmailSubscription.objects.get(id=delete_id)
                email = subscriber.email
                subscriber.delete()
                messages.success(request, f"Successfully deleted subscriber: {email}")
            elif delete_action == "user":
                user = User.objects.get(id=delete_id)
                # Prevent deleting staff users
                if user.is_staff:
                    messages.error(request, "Cannot delete staff users")
                else:
                    username = user.username
                    user.delete()
                    messages.success(request, f"Successfully deleted user: {username}")
        except EmailSubscription.DoesNotExist:
            messages.error(request, "Subscriber not found")
        except User.DoesNotExist:
            messages.error(request, "User not found")
        except Exception as e:
            messages.error(request, f"Error deleting: {str(e)}")

        return redirect("admin_subscribers")

    # Handle Single Subscriber Addition
    if request.method == "POST" and request.POST.get("single_email"):
        email = request.POST.get("single_email", "").strip().lower()

        if email:
            try:
                subscriber, created = EmailSubscription.objects.get_or_create(
                    email=email, defaults={"source": "admin_manual", "is_confirmed": False}
                )
                if created:
                    messages.success(request, f"Successfully added {email}")
                else:
                    messages.info(request, f"{email} is already subscribed")
            except Exception as e:
                messages.error(request, f"Error adding subscriber: {str(e)}")
        else:
            messages.error(request, "Please provide a valid email address")

        return redirect("admin_subscribers")

    # Handle Subscriber CSV Upload
    if request.method == "POST" and request.FILES.get("subscriber_csv"):
        csv_file = request.FILES["subscriber_csv"]

        # Validate file extension
        if not csv_file.name.endswith(".csv"):
            messages.error(request, "Please upload a CSV file.")
            return redirect("admin_subscribers")

        try:
            # Read CSV file
            decoded_file = csv_file.read().decode("utf-8")
            io_string = io.StringIO(decoded_file)
            csv_reader = csv.DictReader(io_string)

            added_count = 0
            skipped_count = 0
            errors = []

            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 (row 1 is header)
                email = row.get("email", "").strip().lower()
                is_confirmed = row.get("is_confirmed", "").strip().lower() in ["true", "1", "yes"]
                source = row.get("source", "csv_upload").strip() or "csv_upload"

                if not email:
                    errors.append(f"Row {row_num}: Missing email")
                    continue

                # Create or get subscriber
                try:
                    sub, created = EmailSubscription.objects.get_or_create(
                        email=email, defaults={"source": source, "is_confirmed": is_confirmed}
                    )
                    if created:
                        added_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    errors.append(f"Row {row_num} ({email}): {str(e)}")

            # Display results
            if added_count > 0:
                messages.success(request, f"Successfully added {added_count} new subscriber(s).")
            if skipped_count > 0:
                messages.info(request, f"Skipped {skipped_count} existing subscriber(s).")
            if errors:
                for error in errors[:5]:  # Show first 5 errors
                    messages.warning(request, error)
                if len(errors) > 5:
                    messages.warning(request, f"...and {len(errors) - 5} more errors.")

            return redirect("admin_subscribers")

        except Exception as e:
            messages.error(request, f"Error processing CSV: {str(e)}")
            return redirect("admin_subscribers")

    # Handle User CSV Upload
    if request.method == "POST" and request.FILES.get("user_csv"):
        csv_file = request.FILES["user_csv"]

        # Validate file extension
        if not csv_file.name.endswith(".csv"):
            messages.error(request, "Please upload a CSV file.")
            return redirect("admin_subscribers")

        try:
            # Read CSV file
            decoded_file = csv_file.read().decode("utf-8")
            io_string = io.StringIO(decoded_file)
            csv_reader = csv.DictReader(io_string)

            added_count = 0
            skipped_count = 0
            errors = []

            for row_num, row in enumerate(csv_reader, start=2):
                username = row.get("username", "").strip()
                email = row.get("email", "").strip().lower()
                password = row.get("password", "").strip() or User.objects.make_random_password()

                if not username or not email:
                    errors.append(f"Row {row_num}: Missing username or email")
                    continue

                # Create user if doesn't exist
                try:
                    user, created = User.objects.get_or_create(
                        username=username,
                        defaults={
                            "email": email,
                        },
                    )
                    if created:
                        user.set_password(password)
                        user.save()
                        added_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    errors.append(f"Row {row_num} ({username}): {str(e)}")

            # Display results
            if added_count > 0:
                messages.success(request, f"Successfully added {added_count} new user(s).")
            if skipped_count > 0:
                messages.info(request, f"Skipped {skipped_count} existing user(s).")
            if errors:
                for error in errors[:5]:  # Show first 5 errors
                    messages.warning(request, error)
                if len(errors) > 5:
                    messages.warning(request, f"...and {len(errors) - 5} more errors.")

            return redirect("admin_subscribers")

        except Exception as e:
            messages.error(request, f"Error processing CSV: {str(e)}")
            return redirect("admin_subscribers")

    # Handle CSV export
    if request.GET.get("export"):
        import csv

        from django.http import HttpResponse

        from shop.models import SMSSubscription

        export_type = request.GET.get("export")
        response = HttpResponse(content_type="text/csv")

        if export_type == "email":
            response["Content-Disposition"] = 'attachment; filename="email_subscribers.csv"'
            writer = csv.writer(response)
            writer.writerow(["Email", "Confirmed", "Active", "Source", "Subscribed At"])

            for sub in EmailSubscription.objects.all().order_by("-subscribed_at"):
                writer.writerow(
                    [
                        sub.email,
                        "Yes" if sub.is_confirmed else "No",
                        "Yes" if sub.is_active else "No",
                        sub.source,
                        sub.subscribed_at.strftime("%Y-%m-%d %H:%M:%S"),
                    ]
                )
        elif export_type == "sms":
            response["Content-Disposition"] = 'attachment; filename="sms_subscribers.csv"'
            writer = csv.writer(response)
            writer.writerow(["Phone Number", "Confirmed", "Active", "Source", "Subscribed At"])

            for sub in SMSSubscription.objects.all().order_by("-subscribed_at"):
                writer.writerow(
                    [
                        sub.phone_number,
                        "Yes" if sub.is_confirmed else "No",
                        "Yes" if sub.is_active else "No",
                        sub.source,
                        sub.subscribed_at.strftime("%Y-%m-%d %H:%M:%S"),
                    ]
                )
        else:  # all
            response["Content-Disposition"] = 'attachment; filename="all_subscribers.csv"'
            writer = csv.writer(response)
            writer.writerow(["Type", "Contact", "Confirmed", "Active", "Source", "Subscribed At"])

            # Combine both lists
            all_subs = []
            for sub in EmailSubscription.objects.all():
                all_subs.append(
                    (
                        "Email",
                        sub.email,
                        sub.is_confirmed,
                        sub.is_active,
                        sub.source,
                        sub.subscribed_at,
                    )
                )
            for sub in SMSSubscription.objects.all():
                all_subs.append(
                    (
                        "SMS",
                        sub.phone_number,
                        sub.is_confirmed,
                        sub.is_active,
                        sub.source,
                        sub.subscribed_at,
                    )
                )

            # Sort by subscribed_at descending
            all_subs.sort(key=lambda x: x[5], reverse=True)

            for sub in all_subs:
                writer.writerow(
                    [
                        sub[0],
                        sub[1],
                        "Yes" if sub[2] else "No",
                        "Yes" if sub[3] else "No",
                        sub[4],
                        sub[5].strftime("%Y-%m-%d %H:%M:%S"),
                    ]
                )

        return response

    # GET request - display all subscribers (both email and SMS)
    import json
    from itertools import chain
    from operator import attrgetter

    from shop.models import SMSSubscription

    # Get all email subscribers
    email_subscribers = EmailSubscription.objects.all().order_by("-subscribed_at")

    # Get all SMS subscribers
    sms_subscribers = SMSSubscription.objects.all().order_by("-subscribed_at")

    # Get unique count (people who may have both email and SMS)
    # For now, just count total unique records
    total_unique = email_subscribers.count() + sms_subscribers.count()

    # Get new subscribers in last 24 hours
    last_24h = timezone.now() - timedelta(hours=24)
    new_24h = (
        email_subscribers.filter(subscribed_at__gte=last_24h).count()
        + sms_subscribers.filter(subscribed_at__gte=last_24h).count()
    )

    # Generate chart data for different timeframes
    def generate_chart_data(days):
        from datetime import datetime, timedelta

        from django.db.models import Count
        from django.db.models.functions import TruncDate

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Get email subscriber counts by date
        email_data = (
            EmailSubscription.objects.filter(subscribed_at__gte=start_date)
            .annotate(date=TruncDate("subscribed_at"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        # Get SMS subscriber counts by date
        sms_data = (
            SMSSubscription.objects.filter(subscribed_at__gte=start_date)
            .annotate(date=TruncDate("subscribed_at"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        # Create complete date range with zero counts for missing days
        date_dict_email = {}
        date_dict_sms = {}

        for i in range(days + 1):
            date = (start_date + timedelta(days=i)).date()
            date_dict_email[date] = 0
            date_dict_sms[date] = 0

        # Fill in actual counts
        for entry in email_data:
            date_dict_email[entry["date"]] = entry["count"]

        for entry in sms_data:
            date_dict_sms[entry["date"]] = entry["count"]

        # Generate labels and data arrays
        labels = []
        email_counts = []
        sms_counts = []

        for date in sorted(date_dict_email.keys()):
            if days <= 7:
                labels.append(date.strftime("%b %d"))
            elif days <= 90:
                labels.append(date.strftime("%m/%d"))
            else:
                labels.append(date.strftime("%b %d"))

            email_counts.append(date_dict_email[date])
            sms_counts.append(date_dict_sms[date])

        return {"labels": labels, "email": email_counts, "sms": sms_counts}

    # Generate chart data for all timeframes
    chart_data_7 = generate_chart_data(7)
    chart_data_30 = generate_chart_data(30)
    chart_data_90 = generate_chart_data(90)
    chart_data_365 = generate_chart_data(365)

    # Generate subscriber status breakdown data
    from django.db.models import Count, Q

    # Count different status categories across both email and SMS
    active_confirmed = (
        EmailSubscription.objects.filter(is_active=True, is_confirmed=True).count()
        + SMSSubscription.objects.filter(is_active=True, is_confirmed=True).count()
    )

    active_unconfirmed = (
        EmailSubscription.objects.filter(is_active=True, is_confirmed=False).count()
        + SMSSubscription.objects.filter(is_active=True, is_confirmed=False).count()
    )

    inactive = (
        EmailSubscription.objects.filter(is_active=False).count()
        + SMSSubscription.objects.filter(is_active=False).count()
    )

    # Format for chart
    status_data = {
        "labels": ["Active & Confirmed", "Active & Unconfirmed", "Inactive"],
        "values": [active_confirmed, active_unconfirmed, inactive],
    }

    # Get recent activity (last 20 subscribers from both email and SMS)
    recent_email = list(email_subscribers[:20])
    recent_sms = list(sms_subscribers[:20])

    # Combine and annotate with type
    recent_activity = []
    for sub in recent_email:
        recent_activity.append(
            {
                "type": "email",
                "contact": sub.email,
                "source": sub.source,
                "subscribed_at": sub.subscribed_at,
            }
        )
    for sub in recent_sms:
        recent_activity.append(
            {
                "type": "sms",
                "contact": sub.phone_number,
                "source": sub.source,
                "subscribed_at": sub.subscribed_at,
            }
        )

    # Sort by subscribed_at and take top 20
    recent_activity.sort(key=lambda x: x["subscribed_at"], reverse=True)
    recent_activity = recent_activity[:20]

    context = {
        "email_subscribers": email_subscribers,
        "sms_subscribers": sms_subscribers,
        "total_unique": total_unique,
        "new_24h": new_24h,
        "chart_data_7": json.dumps(chart_data_7),
        "chart_data_30": json.dumps(chart_data_30),
        "chart_data_90": json.dumps(chart_data_90),
        "chart_data_365": json.dumps(chart_data_365),
        "status_data": json.dumps(status_data),
        "recent_activity": recent_activity,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/subscribers_list.html", context)


@staff_member_required
def security_dashboard(request):
    """
    Display security and system stats dashboard.
    Only accessible to admin/staff users.
    """
    import os
    import platform
    import sys
    from datetime import datetime

    import django
    from django.conf import settings

    import psutil

    now = timezone.now()

    # System Information
    system_info = {
        "python_version": sys.version.split()[0],
        "django_version": django.get_version(),
        "platform": platform.platform(),
        "platform_system": platform.system(),
        "platform_release": platform.release(),
        "processor": platform.processor(),
        "architecture": platform.machine(),
        "hostname": platform.node(),
        "server_time": now,
    }

    # Machine Status (CPU, Memory, Disk)
    try:
        # Use interval=0 for instant CPU reading (non-blocking)
        cpu_percent = psutil.cpu_percent(interval=0)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        machine_status = {
            "cpu_percent": round(cpu_percent, 1),
            "cpu_count": psutil.cpu_count(),
            "memory_total_gb": round(memory.total / (1024**3), 2),
            "memory_used_gb": round(memory.used / (1024**3), 2),
            "memory_percent": round(memory.percent, 1),
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "disk_used_gb": round(disk.used / (1024**3), 2),
            "disk_percent": round(disk.percent, 1),
        }
    except:
        machine_status = {
            "cpu_percent": "N/A",
            "cpu_count": "N/A",
            "memory_total_gb": "N/A",
            "memory_used_gb": "N/A",
            "memory_percent": "N/A",
            "disk_total_gb": "N/A",
            "disk_used_gb": "N/A",
            "disk_percent": "N/A",
        }

    # Database Information
    try:
        from django.db import connection

        db_info = {
            "engine": settings.DATABASES["default"]["ENGINE"].split(".")[-1],
            "name": settings.DATABASES["default"]["NAME"],
            "host": settings.DATABASES["default"].get("HOST", "localhost"),
            "port": settings.DATABASES["default"].get("PORT", "default"),
        }

        # Get database size if PostgreSQL
        if "postgresql" in settings.DATABASES["default"]["ENGINE"]:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_database_size(current_database());")
                db_size_bytes = cursor.fetchone()[0]
                db_size_mb = round(db_size_bytes / (1024 * 1024), 2)
                db_info["size"] = f"{db_size_mb} MB"
        else:
            db_info["size"] = "N/A"
    except Exception as e:
        db_info = {
            "engine": "Unknown",
            "name": "Unknown",
            "host": "Unknown",
            "port": "Unknown",
            "size": "N/A",
            "error": str(e),
        }

    # Django Settings Security Check
    django_settings = {
        "debug_mode": settings.DEBUG,
        "allowed_hosts": settings.ALLOWED_HOSTS,
        "secret_key_set": bool(settings.SECRET_KEY and len(settings.SECRET_KEY) > 20),
        "session_cookie_secure": getattr(settings, "SESSION_COOKIE_SECURE", False),
        "csrf_cookie_secure": getattr(settings, "CSRF_COOKIE_SECURE", False),
        "secure_ssl_redirect": getattr(settings, "SECURE_SSL_REDIRECT", False),
        "secure_hsts_seconds": getattr(settings, "SECURE_HSTS_SECONDS", 0),
        "static_root": bool(getattr(settings, "STATIC_ROOT", None)),
        "media_root": bool(getattr(settings, "MEDIA_ROOT", None)),
    }

    # HTTPS/TLS Status
    https_status = {
        "ssl_redirect": django_settings["secure_ssl_redirect"],
        "session_cookie_secure": django_settings["session_cookie_secure"],
        "csrf_cookie_secure": django_settings["csrf_cookie_secure"],
        "hsts_enabled": django_settings["secure_hsts_seconds"] > 0,
        "hsts_seconds": django_settings["secure_hsts_seconds"],
    }

    # Services Status (check if common services are running)
    services_status = []

    # Check if running under systemd/gunicorn - cache process list
    try:
        # Get process names once and cache
        running_processes = []
        process_count = 0
        for p in psutil.process_iter(["name"]):
            try:
                running_processes.append(p.info["name"].lower())
                process_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        services_status.append(
            {
                "name": "Gunicorn",
                "status": (
                    "running"
                    if any("gunicorn" in p for p in running_processes)
                    else "not detected"
                ),
            }
        )
        services_status.append(
            {
                "name": "Nginx",
                "status": (
                    "running"
                    if any("nginx" in p for p in running_processes)
                    else "not detected"
                ),
            }
        )
        services_status.append(
            {
                "name": "PostgreSQL",
                "status": (
                    "running"
                    if any("postgres" in p for p in running_processes)
                    else "not detected"
                ),
            }
        )
    except:
        services_status.append(
            {
                "name": "Process Check",
                "status": "unavailable",
            }
        )
        process_count = 0

    # Security Warnings
    warnings = []

    if django_settings["debug_mode"]:
        warnings.append(
            {
                "level": "danger",
                "message": "DEBUG mode is enabled! This should be disabled in production.",
            }
        )

    if not django_settings["secret_key_set"]:
        warnings.append({"level": "danger", "message": "SECRET_KEY is not properly configured."})

    if not https_status["ssl_redirect"]:
        warnings.append(
            {
                "level": "warning",
                "message": "SECURE_SSL_REDIRECT is not enabled. HTTPS is not enforced.",
            }
        )

    if not https_status["session_cookie_secure"]:
        warnings.append(
            {
                "level": "warning",
                "message": "SESSION_COOKIE_SECURE is False. Session cookies can be sent over HTTP.",
            }
        )

    if not https_status["hsts_enabled"]:
        warnings.append(
            {"level": "warning", "message": "HSTS (HTTP Strict Transport Security) is not enabled."}
        )

    if settings.ALLOWED_HOSTS == ["*"]:
        warnings.append(
            {
                "level": "danger",
                "message": "ALLOWED_HOSTS is set to ['*']. This is insecure in production.",
            }
        )

    # System resource warnings
    if machine_status["cpu_percent"] != "N/A" and machine_status["cpu_percent"] > 80:
        warnings.append(
            {"level": "warning", "message": f'High CPU usage: {machine_status["cpu_percent"]}%'}
        )

    if machine_status["memory_percent"] != "N/A" and machine_status["memory_percent"] > 85:
        warnings.append(
            {
                "level": "warning",
                "message": f'High memory usage: {machine_status["memory_percent"]}%',
            }
        )

    if machine_status["disk_percent"] != "N/A" and machine_status["disk_percent"] > 90:
        warnings.append(
            {
                "level": "danger",
                "message": f'Critical disk usage: {machine_status["disk_percent"]}%',
            }
        )

    # Get process info (reuse process_count from above)
    try:
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime_seconds = (now - timezone.make_aware(boot_time)).total_seconds()
        uptime_days = int(uptime_seconds // 86400)
        uptime_hours = int((uptime_seconds % 86400) // 3600)
        uptime_minutes = int((uptime_seconds % 3600) // 60)

        system_info["uptime"] = f"{uptime_days}d {uptime_hours}h {uptime_minutes}m"
        system_info["boot_time"] = boot_time
        system_info["process_count"] = process_count if process_count > 0 else "N/A"
    except:
        system_info["uptime"] = "N/A"
        system_info["boot_time"] = "N/A"
        system_info["process_count"] = "N/A"

    # Network info
    try:
        import socket

        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        system_info["local_ip"] = local_ip
    except:
        system_info["local_ip"] = "N/A"

    # Additional metrics for user activity
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    staff_users = User.objects.filter(is_staff=True).count()

    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    recent_users_24h = User.objects.filter(date_joined__gte=last_24h).count()
    recent_users_7d = User.objects.filter(date_joined__gte=last_7d).count()

    user_metrics = {
        "total": total_users,
        "active": active_users,
        "staff": staff_users,
        "recent_24h": recent_users_24h,
        "recent_7d": recent_users_7d,
    }

    # Get recent connections from database
    recent_connections = ConnectionLog.objects.select_related("user").all()[:50]

    # Get unique IPs in last 24 hours
    unique_ips_24h = (
        ConnectionLog.objects.filter(timestamp__gte=last_24h)
        .values("ip_address")
        .distinct()
        .count()
    )

    # Get recent user logins (last login data)
    recent_logins = User.objects.exclude(last_login__isnull=True).order_by("-last_login")[:20]

    # Try to get request logs (if available)
    recent_logs = []
    try:
        import glob
        import os

        log_files = []

        # Common Django log locations
        possible_log_paths = [
            "/var/log/django/*.log",
            "/var/log/gunicorn/*.log",
            "/var/log/nginx/access.log",
            "logs/*.log",
            "*.log",
        ]

        for pattern in possible_log_paths:
            log_files.extend(glob.glob(pattern))

        if log_files:
            # Read last 50 lines from the most recent log file
            latest_log = max(log_files, key=os.path.getmtime)
            with open(latest_log, "r") as f:
                lines = f.readlines()
                recent_logs = lines[-50:]  # Last 50 lines
        else:
            recent_logs = ["No log files found in standard locations"]
    except Exception as e:
        recent_logs = [f"Unable to read logs: {str(e)}"]

    # Email subscription metrics
    total_subs = EmailSubscription.objects.count()
    confirmed_subs = EmailSubscription.objects.filter(is_confirmed=True).count()
    recent_subs_24h = EmailSubscription.objects.filter(subscribed_at__gte=last_24h).count()

    email_metrics = {
        "total": total_subs,
        "confirmed": confirmed_subs,
        "recent_24h": recent_subs_24h,
        "confirmation_rate": round((confirmed_subs / total_subs * 100), 1) if total_subs > 0 else 0,
    }

    context = {
        "system_info": system_info,
        "machine_status": machine_status,
        "db_info": db_info,
        "django_settings": django_settings,
        "https_status": https_status,
        "services_status": services_status,
        "warnings": warnings,
        "user_metrics": user_metrics,
        "email_metrics": email_metrics,
        "recent_logins": recent_logins,
        "recent_logs": recent_logs,
        "recent_connections": recent_connections,
        "unique_ips_24h": unique_ips_24h,
    }

    return render(request, "admin/security_dashboard.html", context)


@staff_member_required
def sms_dashboard(request):
    """
    SMS Marketing dashboard for managing subscribers, templates, and campaigns.
    Only accessible to admin/staff users.
    """
    from .utils.twilio_helper import send_campaign

    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    # Handle campaign send action
    if request.method == "POST" and request.POST.get("action") == "send_campaign":
        campaign_id = request.POST.get("campaign_id")
        try:
            campaign = SMSCampaign.objects.get(id=campaign_id)
            if campaign.status in ["draft", "scheduled"]:
                result = send_campaign(campaign)
                if "error" in result:
                    messages.error(request, f'Campaign failed: {result["error"]}')
                else:
                    messages.success(
                        request,
                        f'Campaign sent! Sent: {result["sent"]}, Failed: {result["failed"]}',
                    )
            else:
                messages.error(request, f"Campaign cannot be sent (status: {campaign.status})")
        except SMSCampaign.DoesNotExist:
            messages.error(request, "Campaign not found")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")

        return redirect("admin_sms")

    # SMS Subscription metrics
    total_sms_subs = SMSSubscription.objects.count()
    active_sms_subs = SMSSubscription.objects.filter(is_active=True).count()
    confirmed_sms_subs = SMSSubscription.objects.filter(is_confirmed=True).count()
    recent_sms_subs_24h = SMSSubscription.objects.filter(subscribed_at__gte=last_24h).count()
    recent_sms_subs_7d = SMSSubscription.objects.filter(subscribed_at__gte=last_7d).count()

    sms_metrics = {
        "total": total_sms_subs,
        "active": active_sms_subs,
        "confirmed": confirmed_sms_subs,
        "recent_24h": recent_sms_subs_24h,
        "recent_7d": recent_sms_subs_7d,
        "active_rate": (
            round((active_sms_subs / total_sms_subs * 100), 1) if total_sms_subs > 0 else 0
        ),
    }

    # Templates
    templates = SMSTemplate.objects.all().order_by("-updated_at")
    total_templates = templates.count()
    active_templates = templates.filter(is_active=True).count()

    # Campaigns
    campaigns = SMSCampaign.objects.all().order_by("-created_at")[:10]
    total_campaigns = SMSCampaign.objects.count()

    campaign_stats = {
        "total": total_campaigns,
        "draft": SMSCampaign.objects.filter(status="draft").count(),
        "scheduled": SMSCampaign.objects.filter(status="scheduled").count(),
        "sent": SMSCampaign.objects.filter(status="sent").count(),
    }

    # Recent SMS logs
    recent_logs = SMSLog.objects.select_related("subscription", "campaign", "template").order_by(
        "-sent_at"
    )[:20]

    # SMS stats by status
    total_sms_sent = SMSLog.objects.count()
    sms_delivered = SMSLog.objects.filter(status="delivered").count()
    sms_failed = SMSLog.objects.filter(status="failed").count()
    sms_sent_24h = SMSLog.objects.filter(sent_at__gte=last_24h).count()

    sms_log_stats = {
        "total": total_sms_sent,
        "delivered": sms_delivered,
        "failed": sms_failed,
        "sent_24h": sms_sent_24h,
        "delivery_rate": (
            round((sms_delivered / total_sms_sent * 100), 1) if total_sms_sent > 0 else 0
        ),
    }

    # Recent subscribers
    recent_subscribers = SMSSubscription.objects.order_by("-subscribed_at")[:10]

    # Chart data for subscriber growth (last 30 days)
    subscriber_growth = []
    for i in range(30, -1, -1):
        date = (now - timedelta(days=i)).date()
        count = SMSSubscription.objects.filter(subscribed_at__date=date).count()
        subscriber_growth.append({"date": date.strftime("%m/%d"), "count": count})

    context = {
        "sms_metrics": sms_metrics,
        "templates": templates,
        "total_templates": total_templates,
        "active_templates": active_templates,
        "campaigns": campaigns,
        "campaign_stats": campaign_stats,
        "recent_logs": recent_logs,
        "sms_log_stats": sms_log_stats,
        "recent_subscribers": recent_subscribers,
        "subscriber_growth": subscriber_growth,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/sms_dashboard.html", context)


@staff_member_required
def email_dashboard(request):
    """
    Email Marketing dashboard for managing subscribers, templates, and campaigns.
    Only accessible to admin/staff users.
    """
    from .utils.email_helper import send_campaign

    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    # Handle campaign send action
    if request.method == "POST" and request.POST.get("action") == "send_campaign":
        campaign_id = request.POST.get("campaign_id")
        try:
            campaign = EmailCampaign.objects.get(id=campaign_id)
            if campaign.status in ["draft", "scheduled"]:
                result = send_campaign(campaign)
                if "error" in result:
                    messages.error(request, f'Campaign failed: {result["error"]}')
                else:
                    messages.success(
                        request,
                        f'Campaign sent! Sent: {result["sent"]}, Failed: {result["failed"]}',
                    )
            else:
                messages.error(request, f"Campaign cannot be sent (status: {campaign.status})")
        except EmailCampaign.DoesNotExist:
            messages.error(request, "Campaign not found")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")

        return redirect("admin_email")

    # Email Subscription metrics
    total_email_subs = EmailSubscription.objects.count()
    active_email_subs = EmailSubscription.objects.filter(is_active=True).count()
    confirmed_email_subs = EmailSubscription.objects.filter(is_confirmed=True).count()
    recent_email_subs_24h = EmailSubscription.objects.filter(subscribed_at__gte=last_24h).count()
    recent_email_subs_7d = EmailSubscription.objects.filter(subscribed_at__gte=last_7d).count()

    email_metrics = {
        "total": total_email_subs,
        "active": active_email_subs,
        "confirmed": confirmed_email_subs,
        "recent_24h": recent_email_subs_24h,
        "recent_7d": recent_email_subs_7d,
        "active_rate": (
            round((active_email_subs / total_email_subs * 100), 1) if total_email_subs > 0 else 0
        ),
    }

    # Templates
    templates = EmailTemplate.objects.all().order_by("-updated_at")
    total_templates = templates.count()
    active_templates = templates.filter(is_active=True).count()

    # Campaigns
    campaigns = EmailCampaign.objects.all().order_by("-created_at")[:10]
    total_campaigns = EmailCampaign.objects.count()

    campaign_stats = {
        "total": total_campaigns,
        "draft": EmailCampaign.objects.filter(status="draft").count(),
        "scheduled": EmailCampaign.objects.filter(status="scheduled").count(),
        "sent": EmailCampaign.objects.filter(status="sent").count(),
    }

    # Recent email logs
    recent_logs = EmailLog.objects.select_related("subscription", "campaign", "template").order_by(
        "-sent_at"
    )[:20]

    # Email stats by status
    total_emails_sent = EmailLog.objects.count()
    emails_delivered = EmailLog.objects.filter(status="delivered").count()
    emails_failed = EmailLog.objects.filter(status="failed").count()
    emails_sent_24h = EmailLog.objects.filter(sent_at__gte=last_24h).count()

    email_log_stats = {
        "total": total_emails_sent,
        "delivered": emails_delivered,
        "failed": emails_failed,
        "sent_24h": emails_sent_24h,
        "delivery_rate": (
            round((emails_delivered / total_emails_sent * 100), 1) if total_emails_sent > 0 else 0
        ),
    }

    # Recent subscribers
    recent_subscribers = EmailSubscription.objects.order_by("-subscribed_at")[:10]

    # Chart data for subscriber growth (last 30 days)
    subscriber_growth = []
    for i in range(30, -1, -1):
        date = (now - timedelta(days=i)).date()
        count = EmailSubscription.objects.filter(subscribed_at__date=date).count()
        subscriber_growth.append({"date": date.strftime("%m/%d"), "count": count})

    context = {
        "email_metrics": email_metrics,
        "templates": templates,
        "total_templates": total_templates,
        "active_templates": active_templates,
        "campaigns": campaigns,
        "campaign_stats": campaign_stats,
        "recent_logs": recent_logs,
        "email_log_stats": email_log_stats,
        "recent_subscribers": recent_subscribers,
        "subscriber_growth": subscriber_growth,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/email_dashboard.html", context)


@staff_member_required
def sms_campaigns(request):
    """
    SMS Campaign management page with create/edit functionality.
    """
    # Handle create/edit
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create":
            name = request.POST.get("name")
            template_id = request.POST.get("template")
            scheduled_at = request.POST.get("scheduled_at")
            notes = request.POST.get("notes", "")

            try:
                template = SMSTemplate.objects.get(id=template_id)
                campaign = SMSCampaign.objects.create(
                    name=name,
                    template=template,
                    scheduled_at=scheduled_at if scheduled_at else None,
                    status="scheduled" if scheduled_at else "draft",
                    notes=notes,
                    created_by=request.user,
                )
                messages.success(request, f'Campaign "{campaign.name}" created successfully!')
                return redirect("admin_sms_campaigns")
            except Exception as e:
                messages.error(request, f"Error creating campaign: {str(e)}")

        elif action == "delete":
            campaign_id = request.POST.get("campaign_id")
            try:
                campaign = SMSCampaign.objects.get(id=campaign_id)
                campaign.delete()
                messages.success(request, "Campaign deleted successfully!")
            except Exception as e:
                messages.error(request, f"Error deleting campaign: {str(e)}")
            return redirect("admin_sms_campaigns")

    # Get all campaigns
    campaigns = SMSCampaign.objects.all().order_by("-created_at")
    templates = SMSTemplate.objects.filter(is_active=True).order_by("name")

    context = {
        "campaigns": campaigns,
        "templates": templates,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/sms_campaigns.html", context)


@staff_member_required
def email_campaigns(request):
    """
    Email Campaign management page with create/edit functionality.
    """
    # Handle create/edit
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create":
            name = request.POST.get("name")
            template_id = request.POST.get("template")
            scheduled_at = request.POST.get("scheduled_at")
            notes = request.POST.get("notes", "")

            try:
                template = EmailTemplate.objects.get(id=template_id)
                campaign = EmailCampaign.objects.create(
                    name=name,
                    template=template,
                    scheduled_at=scheduled_at if scheduled_at else None,
                    status="scheduled" if scheduled_at else "draft",
                    notes=notes,
                    created_by=request.user,
                )
                messages.success(request, f'Campaign "{campaign.name}" created successfully!')
                return redirect("admin_email_campaigns")
            except Exception as e:
                messages.error(request, f"Error creating campaign: {str(e)}")

        elif action == "delete":
            campaign_id = request.POST.get("campaign_id")
            try:
                campaign = EmailCampaign.objects.get(id=campaign_id)
                campaign.delete()
                messages.success(request, "Campaign deleted successfully!")
            except Exception as e:
                messages.error(request, f"Error deleting campaign: {str(e)}")
            return redirect("admin_email_campaigns")

    # Get all campaigns
    campaigns = EmailCampaign.objects.all().order_by("-created_at")
    templates = EmailTemplate.objects.filter(is_active=True).order_by("name")

    context = {
        "campaigns": campaigns,
        "templates": templates,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/email_campaigns.html", context)


@staff_member_required
def sms_templates(request):
    """
    SMS Template management page with create/edit functionality.
    """
    # Handle create/edit
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create":
            name = request.POST.get("name")
            template_type = request.POST.get("template_type")
            auto_trigger = request.POST.get("auto_trigger")
            message_body = request.POST.get("message_body")
            tags = request.POST.get("tags", "")
            notes = request.POST.get("notes", "")

            try:
                template = SMSTemplate.objects.create(
                    name=name,
                    template_type=template_type,
                    auto_trigger=auto_trigger,
                    message_body=message_body,
                    tags=tags,
                    notes=notes,
                    created_by=request.user,
                )
                messages.success(request, f'Template "{template.name}" created successfully!')
                return redirect("admin_sms_templates")
            except Exception as e:
                messages.error(request, f"Error creating template: {str(e)}")

        elif action == "update":
            template_id = request.POST.get("template_id")
            try:
                template = SMSTemplate.objects.get(id=template_id)
                template.name = request.POST.get("name")
                template.template_type = request.POST.get("template_type")
                template.auto_trigger = request.POST.get("auto_trigger")
                template.message_body = request.POST.get("message_body")
                template.tags = request.POST.get("tags", "")
                template.notes = request.POST.get("notes", "")
                template.is_active = request.POST.get("is_active") == "on"
                template.save()
                messages.success(request, f'Template "{template.name}" updated successfully!')
                return redirect("admin_sms_templates")
            except Exception as e:
                messages.error(request, f"Error updating template: {str(e)}")

        elif action == "delete":
            template_id = request.POST.get("template_id")
            try:
                template = SMSTemplate.objects.get(id=template_id)
                template.delete()
                messages.success(request, "Template deleted successfully!")
            except Exception as e:
                messages.error(request, f"Error deleting template: {str(e)}")
            return redirect("admin_sms_templates")

        elif action == "duplicate":
            template_id = request.POST.get("template_id")
            try:
                original = SMSTemplate.objects.get(id=template_id)
                duplicate = SMSTemplate.objects.create(
                    name=f"Copy of {original.name}",
                    template_type=original.template_type,
                    auto_trigger=original.auto_trigger,
                    message_body=original.message_body,
                    tags=original.tags,
                    notes=original.notes,
                    is_active=False,  # Start as inactive
                    created_by=request.user,
                )
                messages.success(request, f'Template duplicated as "{duplicate.name}"!')
                return redirect("admin_sms_templates")
            except Exception as e:
                messages.error(request, f"Error duplicating template: {str(e)}")
            return redirect("admin_sms_templates")

        elif action == "bulk_activate":
            template_ids = request.POST.getlist("template_ids")
            try:
                count = SMSTemplate.objects.filter(id__in=template_ids).update(is_active=True)
                messages.success(request, f"{count} template(s) activated successfully!")
            except Exception as e:
                messages.error(request, f"Error activating templates: {str(e)}")
            return redirect("admin_sms_templates")

        elif action == "bulk_deactivate":
            template_ids = request.POST.getlist("template_ids")
            try:
                count = SMSTemplate.objects.filter(id__in=template_ids).update(is_active=False)
                messages.success(request, f"{count} template(s) deactivated successfully!")
            except Exception as e:
                messages.error(request, f"Error deactivating templates: {str(e)}")
            return redirect("admin_sms_templates")

        elif action == "bulk_delete":
            template_ids = request.POST.getlist("template_ids")
            try:
                count, _ = SMSTemplate.objects.filter(id__in=template_ids).delete()
                messages.success(request, f"{count} template(s) deleted successfully!")
            except Exception as e:
                messages.error(request, f"Error deleting templates: {str(e)}")
            return redirect("admin_sms_templates")

        elif action == "export":
            template_ids = request.POST.getlist("template_ids")
            if template_ids:
                templates_to_export = SMSTemplate.objects.filter(id__in=template_ids)
            else:
                templates_to_export = SMSTemplate.objects.all()

            data = []
            for template in templates_to_export:
                data.append({
                    "name": template.name,
                    "template_type": template.template_type,
                    "auto_trigger": template.auto_trigger,
                    "message_body": template.message_body,
                    "tags": template.tags,
                    "notes": template.notes,
                    "is_active": template.is_active,
                    "times_used": template.times_used,
                })

            response = HttpResponse(json.dumps(data, indent=2), content_type="application/json")
            response["Content-Disposition"] = f'attachment; filename="sms_templates_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json"'
            return response

    # Get template to edit if specified
    edit_template = None
    template_id = request.GET.get("edit")
    if template_id:
        try:
            edit_template = SMSTemplate.objects.get(id=template_id)
        except SMSTemplate.DoesNotExist:
            messages.error(request, "Template not found")

    # Get all templates with sorting
    sort_by = request.GET.get("sort", "-created_at")
    templates = SMSTemplate.objects.all().order_by(sort_by)

    # Calculate stats
    total_count = templates.count()
    active_count = templates.filter(is_active=True).count()
    inactive_count = total_count - active_count
    total_usage = templates.aggregate(total=Sum('times_used'))['total'] or 0

    # Get all unique tags
    all_tags = set()
    for template in templates:
        if template.tags:
            all_tags.update([tag.strip() for tag in template.tags.split(",")])

    # Serialize templates for JavaScript
    templates_json = json.dumps([
        {
            'id': t.id,
            'name': t.name,
            'template_type': t.template_type,
            'auto_trigger': t.auto_trigger,
            'message_body': t.message_body,
            'is_active': t.is_active,
        }
        for t in templates
    ])

    context = {
        "templates": templates,
        "templates_json": templates_json,
        "edit_template": edit_template,
        "template_types": SMSTemplate.TEMPLATE_TYPES,
        "trigger_types": SMSTemplate.TRIGGER_TYPES,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
        "total_count": total_count,
        "active_count": active_count,
        "inactive_count": inactive_count,
        "total_usage": total_usage,
        "all_tags": sorted(all_tags),
        "current_sort": sort_by,
    }

    return render(request, "admin/sms_templates.html", context)


@staff_member_required
def email_templates(request):
    """
    Email Template management page with create/edit functionality.
    """
    # Handle create/edit
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create":
            name = request.POST.get("name")
            template_type = request.POST.get("template_type")
            folder = request.POST.get("folder", "general")
            auto_trigger = request.POST.get("auto_trigger")
            subject = request.POST.get("subject")
            html_body = request.POST.get("html_body")
            text_body = request.POST.get("text_body", "")
            tags = request.POST.get("tags", "")
            notes = request.POST.get("notes", "")
            design_json_str = request.POST.get("design_json", "")

            # Parse design JSON if provided
            design_json = None
            if design_json_str:
                try:
                    design_json = json.loads(design_json_str)
                except json.JSONDecodeError:
                    pass

            try:
                template = EmailTemplate.objects.create(
                    name=name,
                    template_type=template_type,
                    folder=folder,
                    auto_trigger=auto_trigger,
                    subject=subject,
                    html_body=html_body,
                    text_body=text_body,
                    tags=tags,
                    notes=notes,
                    design_json=design_json,
                    created_by=request.user,
                )
                messages.success(request, f'Template "{template.name}" created successfully!')
                return redirect("admin_email_templates")
            except Exception as e:
                messages.error(request, f"Error creating template: {str(e)}")

        elif action == "update":
            template_id = request.POST.get("template_id")
            try:
                template = EmailTemplate.objects.get(id=template_id)
                template.name = request.POST.get("name")
                template.template_type = request.POST.get("template_type")
                template.folder = request.POST.get("folder", "general")
                template.auto_trigger = request.POST.get("auto_trigger")
                template.subject = request.POST.get("subject")
                template.html_body = request.POST.get("html_body")
                template.text_body = request.POST.get("text_body", "")
                template.tags = request.POST.get("tags", "")
                template.notes = request.POST.get("notes", "")
                template.is_active = request.POST.get("is_active") == "on"

                # Update design JSON if provided
                design_json_str = request.POST.get("design_json", "")
                if design_json_str:
                    try:
                        template.design_json = json.loads(design_json_str)
                    except json.JSONDecodeError:
                        pass

                template.save()
                messages.success(request, f'Template "{template.name}" updated successfully!')
                return redirect("admin_email_templates")
            except Exception as e:
                messages.error(request, f"Error updating template: {str(e)}")

        elif action == "delete":
            template_id = request.POST.get("template_id")
            try:
                template = EmailTemplate.objects.get(id=template_id)
                template.delete()
                messages.success(request, "Template deleted successfully!")
            except Exception as e:
                messages.error(request, f"Error deleting template: {str(e)}")
            return redirect("admin_email_templates")

        elif action == "duplicate":
            template_id = request.POST.get("template_id")
            try:
                original = EmailTemplate.objects.get(id=template_id)
                duplicate = EmailTemplate.objects.create(
                    name=f"Copy of {original.name}",
                    template_type=original.template_type,
                    folder=original.folder,
                    auto_trigger=original.auto_trigger,
                    subject=original.subject,
                    html_body=original.html_body,
                    text_body=original.text_body,
                    design_json=original.design_json,
                    tags=original.tags,
                    notes=original.notes,
                    is_active=False,  # Start as inactive
                    created_by=request.user,
                )
                messages.success(request, f'Template duplicated as "{duplicate.name}"!')
                return redirect("admin_email_templates")
            except Exception as e:
                messages.error(request, f"Error duplicating template: {str(e)}")
            return redirect("admin_email_templates")

        elif action == "bulk_activate":
            template_ids = request.POST.getlist("template_ids")
            try:
                count = EmailTemplate.objects.filter(id__in=template_ids).update(is_active=True)
                messages.success(request, f"{count} template(s) activated successfully!")
            except Exception as e:
                messages.error(request, f"Error activating templates: {str(e)}")
            return redirect("admin_email_templates")

        elif action == "bulk_deactivate":
            template_ids = request.POST.getlist("template_ids")
            try:
                count = EmailTemplate.objects.filter(id__in=template_ids).update(is_active=False)
                messages.success(request, f"{count} template(s) deactivated successfully!")
            except Exception as e:
                messages.error(request, f"Error deactivating templates: {str(e)}")
            return redirect("admin_email_templates")

        elif action == "bulk_delete":
            template_ids = request.POST.getlist("template_ids")
            try:
                count, _ = EmailTemplate.objects.filter(id__in=template_ids).delete()
                messages.success(request, f"{count} template(s) deleted successfully!")
            except Exception as e:
                messages.error(request, f"Error deleting templates: {str(e)}")
            return redirect("admin_email_templates")

        elif action == "add_folder":
            folder_name = request.POST.get("folder_name", "").strip()
            if folder_name:
                # Validate folder name
                if len(folder_name) > 50:
                    messages.error(request, "Folder name is too long (max 50 characters)")
                elif folder_name in dict(EmailTemplate.FOLDER_CHOICES):
                    messages.error(request, f'Folder "{folder_name}" already exists as a default folder')
                else:
                    from shop.models import TemplateFolder
                    # Check if folder already exists
                    if TemplateFolder.objects.filter(name=folder_name).exists():
                        messages.error(request, f'Folder "{folder_name}" already exists')
                    else:
                        TemplateFolder.objects.create(
                            name=folder_name.lower().replace(" ", "_"),
                            display_name=folder_name,
                            created_by=request.user,
                        )
                        messages.success(request, f'Folder "{folder_name}" created successfully!')
            else:
                messages.error(request, "Folder name is required")
            return redirect("admin_email_templates")

        elif action == "delete_folder":
            folder_name = request.POST.get("folder_name")
            from shop.models import TemplateFolder
            try:
                # Move all templates from this folder to general
                templates_in_folder = EmailTemplate.objects.filter(folder=folder_name)
                count = templates_in_folder.update(folder="general")

                # Delete the custom folder
                TemplateFolder.objects.filter(name=folder_name).delete()

                if count > 0:
                    messages.success(request, f'Folder deleted and {count} template(s) moved to General')
                else:
                    messages.success(request, 'Folder deleted successfully!')
            except Exception as e:
                messages.error(request, f"Error deleting folder: {str(e)}")
            return redirect("admin_email_templates")

        elif action == "export":
            template_ids = request.POST.getlist("template_ids")
            if template_ids:
                templates_to_export = EmailTemplate.objects.filter(id__in=template_ids)
            else:
                templates_to_export = EmailTemplate.objects.all()

            data = []
            for template in templates_to_export:
                data.append({
                    "name": template.name,
                    "template_type": template.template_type,
                    "auto_trigger": template.auto_trigger,
                    "subject": template.subject,
                    "html_body": template.html_body,
                    "text_body": template.text_body,
                    "tags": template.tags,
                    "notes": template.notes,
                    "is_active": template.is_active,
                    "times_used": template.times_used,
                })

            response = HttpResponse(json.dumps(data, indent=2), content_type="application/json")
            response["Content-Disposition"] = f'attachment; filename="email_templates_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json"'
            return response

    # Get template to edit if specified
    edit_template = None
    template_id = request.GET.get("edit")
    if template_id:
        try:
            edit_template = EmailTemplate.objects.get(id=template_id)
        except EmailTemplate.DoesNotExist:
            messages.error(request, "Template not found")

    # Get all templates with sorting
    sort_by = request.GET.get("sort", "-created_at")
    templates = EmailTemplate.objects.all().order_by(sort_by)

    # Calculate stats
    total_count = templates.count()
    active_count = templates.filter(is_active=True).count()
    inactive_count = total_count - active_count
    total_usage = templates.aggregate(total=Sum('times_used'))['total'] or 0

    # Get all unique tags
    all_tags = set()
    for template in templates:
        if template.tags:
            all_tags.update([tag.strip() for tag in template.tags.split(",")])

    # Serialize templates for JavaScript
    templates_json = json.dumps([
        {
            'id': t.id,
            'name': t.name,
            'template_type': t.template_type,
            'auto_trigger': t.auto_trigger,
            'subject': t.subject,
            'html_body': t.html_body,
            'is_active': t.is_active,
        }
        for t in templates
    ])

    # Get folder statistics for default folders
    folder_counts = {}
    for folder_value, folder_label in EmailTemplate.FOLDER_CHOICES:
        count = templates.filter(folder=folder_value).count()
        folder_counts[folder_value] = {'label': folder_label, 'count': count}

    # Add custom folders
    from shop.models import TemplateFolder
    custom_folders = TemplateFolder.objects.all()
    for custom_folder in custom_folders:
        count = templates.filter(folder=custom_folder.name).count()
        folder_counts[custom_folder.name] = {'label': custom_folder.display_name, 'count': count, 'is_custom': True}

    # Build folder choices list including custom folders
    all_folder_choices = list(EmailTemplate.FOLDER_CHOICES)
    for custom_folder in custom_folders:
        all_folder_choices.append((custom_folder.name, custom_folder.display_name))

    context = {
        "templates": templates,
        "templates_json": templates_json,
        "edit_template": edit_template,
        "template_types": EmailTemplate.TEMPLATE_TYPES,
        "trigger_types": EmailTemplate.TRIGGER_TYPES,
        "folder_choices": all_folder_choices,
        "folder_counts": folder_counts,
        "custom_folders": custom_folders,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
        "total_count": total_count,
        "active_count": active_count,
        "inactive_count": inactive_count,
        "total_usage": total_usage,
        "all_tags": sorted(all_tags),
        "current_sort": sort_by,
    }

    return render(request, "admin/email_templates.html", context)


@staff_member_required
def homepage_settings(request):
    """
    Homepage settings management page for hero image, title, subtitle, and hero slideshow.
    Handles AJAX requests for hero slide management.
    """
    import base64
    import uuid
    from django.core.files.base import ContentFile

    site_settings = SiteSettings.load()

    # Handle AJAX requests for hero slides and quick links
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        action = request.POST.get("action") or request.GET.get("action")

        # For JSON requests, parse body to get action
        if not action and request.content_type == "application/json":
            try:
                body_data = json.loads(request.body)
                action = body_data.get("action")
            except (json.JSONDecodeError, ValueError):
                pass

        if action == "get_slides":
            return JsonResponse({
                "success": True,
                "slides": site_settings.hero_slides or []
            })

        elif action == "save_slides":
            try:
                data = json.loads(request.body)
                slides = data.get("slides", [])
                slideshow_settings = data.get("slideshow_settings", {})
                site_settings.hero_slides = slides
                site_settings.slideshow_settings = slideshow_settings
                site_settings.save()
                return JsonResponse({"success": True})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "upload_slide_image":
            try:
                from shop.utils.image_optimizer import optimize_image
                import io

                image_data = request.POST.get("image_data")
                if not image_data:
                    # Check if data might be in FILES instead
                    if request.FILES:
                        return JsonResponse({"success": False, "error": "Received file upload instead of base64 data"})
                    return JsonResponse({"success": False, "error": "No image data provided. Content length: " + str(request.headers.get('Content-Length', 'unknown'))})

                # Parse base64 data
                if "base64," not in image_data:
                    return JsonResponse({"success": False, "error": "Invalid image format - missing base64 header"})

                format_part, data_part = image_data.split("base64,", 1)

                try:
                    image_content = base64.b64decode(data_part)
                except Exception as decode_err:
                    return JsonResponse({"success": False, "error": f"Failed to decode base64: {decode_err}"})

                if len(image_content) == 0:
                    return JsonResponse({"success": False, "error": "Decoded image is empty"})

                # Optimize image (resize, convert to WebP, compress)
                original_size = len(image_content)
                optimized_content, filename, content_type = optimize_image(
                    io.BytesIO(image_content),
                    filename=f"hero_slide_{uuid.uuid4().hex[:8]}"
                )
                optimized_size = len(optimized_content)

                # Save optimized image to media folder
                from django.core.files.storage import default_storage
                path = default_storage.save(f"site/hero/{filename}", ContentFile(optimized_content))
                url = default_storage.url(path)

                # Log optimization results
                savings = round((1 - optimized_size / original_size) * 100, 1) if original_size > 0 else 0
                logger.info(f"Image optimized: {original_size} -> {optimized_size} bytes ({savings}% reduction)")

                return JsonResponse({"success": True, "url": url})
            except Exception as e:
                import traceback
                return JsonResponse({"success": False, "error": f"{str(e)} - {traceback.format_exc()[:200]}"})

        elif action == "delete_slide_image":
            try:
                data = json.loads(request.body)
                image_url = data.get("image_url", "")
                # Extract path from URL and delete if it's a media file
                if image_url and "/media/" in image_url:
                    from django.core.files.storage import default_storage
                    path = image_url.split("/media/")[-1]
                    if default_storage.exists(path):
                        default_storage.delete(path)
                return JsonResponse({"success": True})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "save_gallery":
            try:
                data = json.loads(request.body)
                gallery_images = data.get("gallery_images", [])
                site_settings.gallery_images = gallery_images
                site_settings.save()
                return JsonResponse({"success": True})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        return JsonResponse({"success": False, "error": "Unknown action"})

    if request.method == "POST":
        # Handle image removal
        if request.POST.get("remove_image") == "true":
            if site_settings.hero_image:
                site_settings.hero_image.delete(save=False)
                site_settings.hero_image = None
                site_settings.save()
                messages.success(request, "Hero image removed successfully!")
                return redirect("admin_homepage")

        # Handle hero image upload (with optimization)
        if "hero_image" in request.FILES:
            from django.core.files.base import ContentFile
            from shop.utils.image_optimizer import optimize_image

            uploaded_file = request.FILES["hero_image"]
            optimized_content, filename, content_type = optimize_image(
                uploaded_file,
                filename=uploaded_file.name
            )
            site_settings.hero_image.save(filename, ContentFile(optimized_content), save=False)

        # Update text fields
        site_settings.hero_title = request.POST.get("hero_title", site_settings.hero_title)
        site_settings.hero_subtitle = request.POST.get("hero_subtitle", site_settings.hero_subtitle)
        site_settings.save()

        messages.success(request, "Homepage settings updated successfully!")
        return redirect("admin_homepage")

    context = {
        "site_settings": site_settings,
        "hero_slides": site_settings.hero_slides or [],
        "gallery_images": site_settings.gallery_images or [],
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/homepage_settings.html", context)


@staff_member_required
def quick_links_settings(request):
    """
    Quick Links management page for external service shortcuts.
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

        if action == "get_quick_links":
            links = QuickLink.objects.all().order_by('display_order', 'name')
            return JsonResponse({
                "success": True,
                "links": [
                    {
                        "id": link.id,
                        "name": link.name,
                        "url": link.url,
                        "icon": link.icon,
                        "username": link.username,
                        "notes": link.notes,
                        "category": link.category,
                        "display_order": link.display_order,
                        "is_active": link.is_active,
                    }
                    for link in links
                ]
            })

        elif action == "save_quick_link":
            try:
                data = json.loads(request.body)
                link_id = data.get("id")
                name = data.get("name", "").strip()
                url = data.get("url", "").strip()
                icon = data.get("icon", "fa-link").strip() or "fa-link"
                username = data.get("username", "").strip()
                notes = data.get("notes", "").strip()
                category = data.get("category", "other")
                display_order = int(data.get("display_order", 0))
                is_active = data.get("is_active", True)

                if not name or not url:
                    return JsonResponse({"success": False, "error": "Name and URL are required"})

                # Auto-add https:// if no protocol specified
                if url and not url.startswith(('http://', 'https://')):
                    url = 'https://' + url

                if link_id:
                    link = QuickLink.objects.get(id=link_id)
                    link.name = name
                    link.url = url
                    link.icon = icon
                    link.username = username
                    link.notes = notes
                    link.category = category
                    link.display_order = display_order
                    link.is_active = is_active
                    link.save()
                else:
                    link = QuickLink.objects.create(
                        name=name,
                        url=url,
                        icon=icon,
                        username=username,
                        notes=notes,
                        category=category,
                        display_order=display_order,
                        is_active=is_active,
                    )

                return JsonResponse({
                    "success": True,
                    "link": {
                        "id": link.id,
                        "name": link.name,
                        "url": link.url,
                        "icon": link.icon,
                        "username": link.username,
                        "notes": link.notes,
                        "category": link.category,
                        "display_order": link.display_order,
                        "is_active": link.is_active,
                    }
                })
            except QuickLink.DoesNotExist:
                return JsonResponse({"success": False, "error": "Link not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "delete_quick_link":
            try:
                data = json.loads(request.body)
                link_id = data.get("id")
                QuickLink.objects.filter(id=link_id).delete()
                return JsonResponse({"success": True})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        return JsonResponse({"success": False, "error": "Unknown action"})

    # Get Quick Links
    quick_links = QuickLink.objects.all().order_by('display_order', 'name')

    context = {
        "quick_links": quick_links,
        "quick_link_categories": QuickLink.CATEGORY_CHOICES,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/quick_links_settings.html", context)


@staff_member_required
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
                        from .utils.email_helper import send_email

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


@staff_member_required
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


@staff_member_required
def all_campaigns(request):
    """
    Unified view showing both email and SMS campaigns together.
    """
    from shop.models import EmailCampaign, SMSCampaign

    # Get all email campaigns
    email_campaigns = EmailCampaign.objects.all().select_related("template")
    email_list = []
    for campaign in email_campaigns:
        email_list.append(
            {
                "id": campaign.id,
                "type": "email",
                "name": campaign.name,
                "template": campaign.template,
                "status": campaign.status,
                "get_status_display": campaign.get_status_display(),
                "scheduled_at": campaign.scheduled_at,
                "total_recipients": campaign.total_recipients,
                "sent_count": campaign.sent_count,
                "created_at": campaign.created_at,
            }
        )

    # Get all SMS campaigns
    sms_campaigns = SMSCampaign.objects.all().select_related("template")
    sms_list = []
    for campaign in sms_campaigns:
        sms_list.append(
            {
                "id": campaign.id,
                "type": "sms",
                "name": campaign.name,
                "template": campaign.template,
                "status": campaign.status,
                "get_status_display": campaign.get_status_display(),
                "scheduled_at": campaign.scheduled_at,
                "total_recipients": campaign.total_recipients,
                "sent_count": campaign.sent_count,
                "created_at": campaign.created_at,
            }
        )

    # Combine and sort by created_at
    all_campaigns_list = email_list + sms_list
    all_campaigns_list.sort(key=lambda x: x["created_at"], reverse=True)

    context = {
        "campaigns": all_campaigns_list,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/all_campaigns.html", context)


@staff_member_required
def campaign_create(request):
    """
    Create and manage unified campaigns containing multiple scheduled email/SMS messages.
    Example: "Fall Sale 2025" campaign with welcome email, follow-up SMS, reminder email.
    """
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create_campaign":
            name = request.POST.get("name")
            description = request.POST.get("description", "")
            target_group = request.POST.get("target_group", "")
            active_from = request.POST.get("active_from")
            active_until = request.POST.get("active_until")

            try:
                campaign = Campaign.objects.create(
                    name=name,
                    description=description,
                    target_group=target_group,
                    active_from=active_from if active_from else None,
                    active_until=active_until if active_until else None,
                    created_by=request.user,
                )
                messages.success(request, f'Campaign "{campaign.name}" created successfully!')
                return redirect("admin_campaign_edit", campaign_id=campaign.id)
            except Exception as e:
                messages.error(request, f"Error creating campaign: {str(e)}")

    # Get all email and SMS templates
    email_templates = EmailTemplate.objects.filter(is_active=True).order_by("name")
    sms_templates = SMSTemplate.objects.filter(is_active=True).order_by("name")

    context = {
        "email_templates": email_templates,
        "sms_templates": sms_templates,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/campaign_create.html", context)


@staff_member_required
def campaign_edit(request, campaign_id):
    """
    Edit campaign and manage its messages.
    """
    try:
        campaign = Campaign.objects.get(id=campaign_id)
    except Campaign.DoesNotExist:
        messages.error(request, "Campaign not found")
        return redirect("admin_campaigns_list")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "update_campaign":
            campaign.name = request.POST.get("name")
            campaign.description = request.POST.get("description", "")
            campaign.target_group = request.POST.get("target_group", "")

            active_from = request.POST.get("active_from")
            active_until = request.POST.get("active_until")
            campaign.active_from = active_from if active_from else None
            campaign.active_until = active_until if active_until else None

            campaign.save()
            messages.success(request, f'Campaign "{campaign.name}" updated successfully!')
            return redirect("admin_campaign_edit", campaign_id=campaign.id)

        elif action == "add_message":
            name = request.POST.get("message_name")
            message_type = request.POST.get("message_type")
            trigger_type = request.POST.get("trigger_type")
            order = request.POST.get("order", 0)
            custom_subject = request.POST.get("custom_subject", "")
            custom_content = request.POST.get("custom_content", "")

            # Get template if specified
            email_template_id = request.POST.get("email_template")
            sms_template_id = request.POST.get("sms_template")

            try:
                message = CampaignMessage.objects.create(
                    campaign=campaign,
                    name=name,
                    message_type=message_type,
                    trigger_type=trigger_type,
                    order=int(order),
                    custom_subject=custom_subject,
                    custom_content=custom_content,
                )

                if message_type == "email" and email_template_id:
                    message.email_template = EmailTemplate.objects.get(id=email_template_id)
                elif message_type == "sms" and sms_template_id:
                    message.sms_template = SMSTemplate.objects.get(id=sms_template_id)

                # Handle delay settings
                if trigger_type == "delay":
                    message.delay_days = int(request.POST.get("delay_days", 0))
                    message.delay_hours = int(request.POST.get("delay_hours", 0))
                elif trigger_type == "specific_date":
                    scheduled_date = request.POST.get("scheduled_date")
                    if scheduled_date:
                        message.scheduled_date = scheduled_date

                message.save()
                messages.success(request, f'Message "{message.name}" added successfully!')
                return redirect("admin_campaign_edit", campaign_id=campaign.id)
            except Exception as e:
                messages.error(request, f"Error adding message: {str(e)}")

        elif action == "delete_message":
            message_id = request.POST.get("message_id")
            try:
                message = CampaignMessage.objects.get(id=message_id, campaign=campaign)
                message.delete()
                messages.success(request, "Message deleted successfully!")
            except Exception as e:
                messages.error(request, f"Error deleting message: {str(e)}")
            return redirect("admin_campaign_edit", campaign_id=campaign.id)

    # Get campaign messages ordered by sequence
    messages_list = campaign.messages.all().order_by("order", "created_at")

    # Get templates
    email_templates = EmailTemplate.objects.filter(is_active=True).order_by("name")
    sms_templates = SMSTemplate.objects.filter(is_active=True).order_by("name")

    context = {
        "campaign": campaign,
        "messages_list": messages_list,
        "email_templates": email_templates,
        "sms_templates": sms_templates,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/campaign_edit.html", context)


@staff_member_required
def products_dashboard(request):
    """
    Products management dashboard.
    """
    from django.db.models import Count, Q, Sum

    from shop.models import Product, ProductVariant

    # Handle product actions
    if request.method == "POST":
        from django.http import JsonResponse

        action = request.POST.get("action")

        # Debug logging
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"POST action received: {action}")

        if action == "toggle_active":
            from django.http import JsonResponse

            product_id = request.POST.get("product_id")
            try:
                product = Product.objects.get(id=product_id)
                product.is_active = not product.is_active
                product.save()
                return JsonResponse({"success": True, "is_active": product.is_active})
            except Product.DoesNotExist:
                return JsonResponse({"success": False, "error": "Product not found"})

        elif action == "upload_product_image":
            # Upload and optimize product image
            from django.core.files.base import ContentFile
            from shop.utils.image_optimizer import optimize_image
            import io

            try:
                image_data = request.POST.get("image_data")
                if not image_data:
                    return JsonResponse({"success": False, "error": "No image data provided"})

                # Parse base64 data
                if "base64," not in image_data:
                    return JsonResponse({"success": False, "error": "Invalid image format"})

                format_part, data_part = image_data.split("base64,", 1)
                image_content = base64.b64decode(data_part)

                if len(image_content) == 0:
                    return JsonResponse({"success": False, "error": "Empty image"})

                # Optimize image (resize, convert to WebP, compress)
                original_size = len(image_content)
                optimized_content, filename, content_type = optimize_image(
                    io.BytesIO(image_content),
                    filename=f"product_{uuid.uuid4().hex[:8]}"
                )
                optimized_size = len(optimized_content)

                # Save to media folder
                from django.core.files.storage import default_storage
                path = default_storage.save(f"products/{filename}", ContentFile(optimized_content))
                url = default_storage.url(path)

                # Log optimization
                savings = round((1 - optimized_size / original_size) * 100, 1) if original_size > 0 else 0
                logger.info(f"Product image optimized: {original_size} -> {optimized_size} bytes ({savings}% reduction)")

                return JsonResponse({"success": True, "url": url})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "create_product":
            import json

            from django.http import JsonResponse
            from django.utils.text import slugify

            from shop.models import Category

            name = request.POST.get("name", "").strip()
            if not name:
                return JsonResponse({"success": False, "error": "Product name is required"})

            # Generate slug from name
            base_slug = slugify(name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            # Get category if provided
            category_slug = request.POST.get("category")
            category_obj = None
            if category_slug:
                try:
                    category_obj = Category.objects.get(slug=category_slug)
                except Category.DoesNotExist:
                    pass

            # Get base price (default to 0 if not provided)
            try:
                base_price = float(request.POST.get("base_price", 0))
            except (ValueError, TypeError):
                base_price = 0

            # Get base cost (default to 0 if not provided)
            try:
                base_cost = float(request.POST.get("base_cost", 0))
            except (ValueError, TypeError):
                base_cost = 0

            # Parse images
            images_json = request.POST.get("images", "[]")
            try:
                images = json.loads(images_json)
            except json.JSONDecodeError:
                images = []

            try:
                # available_for_purchase defaults to True if not specified or if "on" (checkbox value)
                available = request.POST.get("available_for_purchase", "true")
                available_for_purchase = available in ("true", "on", True)

                product = Product.objects.create(
                    name=name,
                    slug=slug,
                    description=request.POST.get("description", ""),
                    base_price=base_price,
                    base_cost=base_cost,
                    category_obj=category_obj,
                    is_active=request.POST.get("is_active") == "true",
                    featured=request.POST.get("featured") in ("true", "on"),
                    available_for_purchase=available_for_purchase,
                    images=images,
                )
                return JsonResponse({"success": True, "product_id": product.id, "slug": product.slug})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_price":
            from django.http import JsonResponse

            product_id = request.POST.get("product_id")
            new_price = request.POST.get("price")
            try:
                product = Product.objects.get(id=product_id)
                product.base_price = new_price
                product.save()
                return JsonResponse({"success": True})
            except Product.DoesNotExist:
                return JsonResponse({"success": False, "error": "Product not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_product":
            import json

            from django.http import JsonResponse

            from shop.models import Category

            product_id = request.POST.get("product_id")
            try:
                from decimal import Decimal

                product = Product.objects.get(id=product_id)

                # Store old base_price to update variants using it
                old_base_price = product.base_price
                new_base_price = Decimal(request.POST.get("base_price"))

                product.name = request.POST.get("name")
                product.slug = request.POST.get("slug")

                # Update category - try to find Category object by slug, fallback to legacy
                category_slug = request.POST.get("category")
                if category_slug:
                    try:
                        category_obj = Category.objects.get(slug=category_slug)
                        product.category_obj = category_obj
                    except Category.DoesNotExist:
                        # Fallback to legacy category field
                        product.category_legacy = category_slug

                product.description = request.POST.get("description")
                product.base_price = new_base_price
                product.base_cost = request.POST.get("base_cost") or 0
                product.featured = request.POST.get("featured") == "true"
                product.available_for_purchase = request.POST.get("available_for_purchase") == "true"

                # Update images
                images_json = request.POST.get("images")
                if images_json is not None:
                    try:
                        product.images = json.loads(images_json)
                    except json.JSONDecodeError:
                        pass

                product.save()

                # Update all variants that were using the old base price to the new base price
                if old_base_price != new_base_price:
                    variants_updated = product.variants.filter(price=old_base_price).update(
                        price=new_base_price
                    )

                return JsonResponse({"success": True})
            except Product.DoesNotExist:
                return JsonResponse({"success": False, "error": "Product not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "get_sizes_colors_materials":
            from django.http import JsonResponse

            from shop.models import Color, Material, Size

            sizes = list(Size.objects.all().values("id", "code", "label"))
            colors = list(Color.objects.all().values("id", "name"))
            materials = list(Material.objects.all().values("id", "name"))

            return JsonResponse(
                {"success": True, "sizes": sizes, "colors": colors, "materials": materials}
            )

        elif action == "get_product_category_attributes":
            from django.http import JsonResponse

            product_id = request.POST.get("product_id")
            try:
                product = Product.objects.get(id=product_id)
                category = product.category_obj

                if not category:
                    return JsonResponse(
                        {"success": False, "error": "Product has no category assigned"}
                    )

                return JsonResponse(
                    {
                        "success": True,
                        "category_name": category.name,
                        "uses_size": category.uses_size,
                        "uses_color": category.uses_color,
                        "uses_material": category.uses_material,
                        "custom_attributes": category.custom_attributes or [],
                        "common_fields": category.common_fields or [],
                    }
                )
            except Product.DoesNotExist:
                return JsonResponse({"success": False, "error": "Product not found"})

        elif action == "get_variants":
            from django.db.models import Sum
            from django.http import JsonResponse

            from shop.models import ShipmentItem

            product_id = request.POST.get("product_id")
            try:
                product = Product.objects.get(id=product_id)
                variants = product.variants.all().select_related("size", "color", "material")

                # Get pending shipment data for all variants in this product
                pending_shipments = ShipmentItem.objects.filter(
                    variant__product=product,
                    shipment__status__in=["pending", "in-transit", "delayed"]
                ).select_related("shipment", "variant")

                # Build lookup of pending items by variant_id
                pending_by_variant = {}
                for item in pending_shipments:
                    if item.variant_id not in pending_by_variant:
                        pending_by_variant[item.variant_id] = []
                    pending_by_variant[item.variant_id].append({
                        "shipment_id": item.shipment.id,
                        "name": item.shipment.name,
                        "tracking": item.shipment.tracking_number,
                        "supplier": item.shipment.supplier,
                        "expected_date": item.shipment.expected_date.isoformat() if item.shipment.expected_date else None,
                        "status": item.shipment.status,
                        "quantity": item.quantity,
                    })

                variants_data = []
                base_price = product.base_price
                base_cost = product.base_cost
                for v in variants:
                    pending_items = pending_by_variant.get(v.id, [])
                    pending_total = sum(item["quantity"] for item in pending_items)
                    # Check if variant has custom price (differs from product base_price)
                    has_custom_price = v.price != base_price if base_price else False
                    # Check if variant has custom cost (has a value set, not null)
                    has_custom_cost = v.cost is not None
                    # Effective cost is variant cost if set, otherwise product base_cost
                    effective_cost = v.cost if v.cost is not None else base_cost
                    variants_data.append({
                        "id": v.id,
                        "sku": v.sku,
                        "size": str(v.size),
                        "size_id": v.size.id,
                        "color": str(v.color),
                        "color_id": v.color.id,
                        "material": str(v.material) if v.material else None,
                        "material_id": v.material.id if v.material else None,
                        "stock_quantity": v.stock_quantity,
                        "price": str(v.price),
                        "has_custom_price": has_custom_price,
                        "cost": str(effective_cost) if effective_cost else "0",
                        "has_custom_cost": has_custom_cost,
                        "is_active": v.is_active,
                        "images": v.images if hasattr(v, "images") else [],
                        "custom_fields": v.custom_fields if hasattr(v, "custom_fields") else {},
                        "pending_shipments": pending_items,
                        "pending_total": pending_total,
                    })

                return JsonResponse({"success": True, "variants": variants_data})
            except Product.DoesNotExist:
                return JsonResponse({"success": False, "error": "Product not found"})

        elif action == "add_variant":
            import json

            from django.http import JsonResponse

            product_id = request.POST.get("product_id")
            size_id = request.POST.get("size_id")
            color_id = request.POST.get("color_id")
            material_id = request.POST.get("material_id")
            sku = request.POST.get("sku", "")
            stock_quantity = request.POST.get("stock_quantity", 0)
            price = request.POST.get("price")
            images_json = request.POST.get("images", "[]")
            custom_fields_json = request.POST.get("custom_fields", "{}")

            try:
                from shop.models import Color, Material, Size

                product = Product.objects.get(id=product_id)
                size = Size.objects.get(id=size_id)
                color = Color.objects.get(id=color_id)
                material = Material.objects.get(id=material_id) if material_id else None

                # Parse JSON data
                try:
                    images = json.loads(images_json)
                    custom_fields = json.loads(custom_fields_json)
                except json.JSONDecodeError:
                    images = []
                    custom_fields = {}

                # Check if variant already exists
                existing = ProductVariant.objects.filter(
                    product=product, size=size, color=color, material=material
                ).first()

                if existing:
                    parts = [str(size), str(color)]
                    if material:
                        parts.append(str(material))
                    return JsonResponse(
                        {"success": False, "error": f'Variant {" - ".join(parts)} already exists'}
                    )

                variant = ProductVariant.objects.create(
                    product=product,
                    size=size,
                    color=color,
                    material=material,
                    sku=sku or None,  # Let model auto-generate if empty
                    stock_quantity=stock_quantity,
                    price=price,
                    images=images,
                    custom_fields=custom_fields,
                    is_active=True,
                )

                return JsonResponse({"success": True})
            except Product.DoesNotExist:
                return JsonResponse({"success": False, "error": "Product not found"})
            except Size.DoesNotExist:
                return JsonResponse({"success": False, "error": "Size not found"})
            except Color.DoesNotExist:
                return JsonResponse({"success": False, "error": "Color not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_variant":
            import json

            from django.http import JsonResponse

            variant_id = request.POST.get("variant_id")
            size_id = request.POST.get("size_id")
            color_id = request.POST.get("color_id")
            material_id = request.POST.get("material_id")
            sku = request.POST.get("sku", "")
            stock_quantity = request.POST.get("stock_quantity", 0)
            price = request.POST.get("price")
            cost = request.POST.get("cost")  # None means use base cost
            use_base_cost = request.POST.get("use_base_cost") == "true"
            images_json = request.POST.get("images", "[]")
            custom_fields_json = request.POST.get("custom_fields", "{}")

            try:
                from shop.models import Color, Material, Size

                variant = ProductVariant.objects.get(id=variant_id)
                size = Size.objects.get(id=size_id)
                color = Color.objects.get(id=color_id)
                material = Material.objects.get(id=material_id) if material_id else None

                try:
                    images = json.loads(images_json)
                    custom_fields = json.loads(custom_fields_json)
                except json.JSONDecodeError:
                    images = []
                    custom_fields = {}

                # Check for duplicate (different variant with same size/color/material)
                existing = ProductVariant.objects.filter(
                    product=variant.product, size=size, color=color, material=material
                ).exclude(id=variant_id).first()

                if existing:
                    parts = [str(size), str(color)]
                    if material:
                        parts.append(str(material))
                    return JsonResponse(
                        {"success": False, "error": f'Variant {" - ".join(parts)} already exists'}
                    )

                variant.size = size
                variant.color = color
                variant.material = material
                variant.sku = sku or None
                variant.stock_quantity = stock_quantity
                variant.price = price
                # Handle cost - None means use base cost, a value means custom cost
                if use_base_cost:
                    variant.cost = None
                elif cost:
                    variant.cost = cost
                variant.images = images
                variant.custom_fields = custom_fields
                variant.save()

                return JsonResponse({"success": True})
            except ProductVariant.DoesNotExist:
                return JsonResponse({"success": False, "error": "Variant not found"})
            except Size.DoesNotExist:
                return JsonResponse({"success": False, "error": "Size not found"})
            except Color.DoesNotExist:
                return JsonResponse({"success": False, "error": "Color not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "bulk_create_variants":
            """
            Create multiple variants at once by selecting multiple sizes and colors.
            This creates all size×color combinations (matrix builder).
            """
            import json

            from django.http import JsonResponse

            product_id = request.POST.get("product_id")
            size_ids = request.POST.getlist("size_ids[]") or json.loads(request.POST.get("size_ids", "[]"))
            color_ids = request.POST.getlist("color_ids[]") or json.loads(request.POST.get("color_ids", "[]"))
            material_id = request.POST.get("material_id")
            price = request.POST.get("price")
            stock_quantity = int(request.POST.get("stock_quantity", 0))

            try:
                from shop.models import Color, Material, Size

                product = Product.objects.get(id=product_id)
                material = Material.objects.get(id=material_id) if material_id else None

                created_count = 0
                skipped_count = 0
                errors = []

                for size_id in size_ids:
                    for color_id in color_ids:
                        try:
                            size = Size.objects.get(id=size_id)
                            color = Color.objects.get(id=color_id)

                            # Check if variant already exists
                            existing = ProductVariant.objects.filter(
                                product=product, size=size, color=color, material=material
                            ).first()

                            if existing:
                                skipped_count += 1
                                continue

                            # Create the variant
                            ProductVariant.objects.create(
                                product=product,
                                size=size,
                                color=color,
                                material=material,
                                stock_quantity=stock_quantity,
                                price=price,
                                images=[],
                                custom_fields={},
                                is_active=True,
                            )
                            created_count += 1
                        except (Size.DoesNotExist, Color.DoesNotExist) as e:
                            errors.append(str(e))
                            continue

                message = f"Created {created_count} variant(s)"
                if skipped_count > 0:
                    message += f", skipped {skipped_count} existing"

                return JsonResponse({
                    "success": True,
                    "created": created_count,
                    "skipped": skipped_count,
                    "message": message
                })
            except Product.DoesNotExist:
                return JsonResponse({"success": False, "error": "Product not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_variant_price":
            from django.http import JsonResponse

            variant_id = request.POST.get("variant_id")
            new_price = request.POST.get("price")

            try:
                variant = ProductVariant.objects.get(id=variant_id)
                variant.price = new_price
                variant.save()
                return JsonResponse({"success": True})
            except ProductVariant.DoesNotExist:
                return JsonResponse({"success": False, "error": "Variant not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "apply_base_price_to_all":
            from django.http import JsonResponse

            product_id = request.POST.get("product_id")

            try:
                product = Product.objects.get(id=product_id)
                base_price = product.base_price

                if not base_price:
                    return JsonResponse({"success": False, "error": "Product has no base price"})

                # Update all variants to use the base price
                updated_count = product.variants.update(price=base_price)

                return JsonResponse({
                    "success": True,
                    "updated_count": updated_count,
                    "base_price": str(base_price)
                })
            except Product.DoesNotExist:
                return JsonResponse({"success": False, "error": "Product not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "toggle_variant_active":
            from django.http import JsonResponse

            variant_id = request.POST.get("variant_id")

            try:
                variant = ProductVariant.objects.get(id=variant_id)
                variant.is_active = not variant.is_active
                variant.save()
                return JsonResponse({"success": True, "is_active": variant.is_active})
            except ProductVariant.DoesNotExist:
                return JsonResponse({"success": False, "error": "Variant not found"})

        elif action == "delete_variant":
            from django.http import JsonResponse

            variant_id = request.POST.get("variant_id")

            try:
                variant = ProductVariant.objects.get(id=variant_id)
                variant.delete()
                return JsonResponse({"success": True})
            except ProductVariant.DoesNotExist:
                return JsonResponse({"success": False, "error": "Variant not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "get_pending_shipments":
            from django.http import JsonResponse

            from shop.models import Shipment

            try:
                shipments = Shipment.objects.filter(
                    status__in=["pending", "in-transit", "delayed"]
                ).order_by("-expected_date")

                shipments_data = [
                    {
                        "id": s.id,
                        "name": s.name,
                        "tracking_number": s.tracking_number,
                        "supplier": s.supplier,
                        "expected_date": s.expected_date.isoformat() if s.expected_date else None,
                        "status": s.status,
                        "item_count": s.item_count,
                    }
                    for s in shipments
                ]

                return JsonResponse({"success": True, "shipments": shipments_data})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "quick_create_shipment":
            import uuid
            from datetime import timedelta

            from django.http import JsonResponse

            from shop.models import Shipment

            supplier = request.POST.get("supplier", "").strip()
            tracking = request.POST.get("tracking_number", "").strip()

            if not supplier:
                return JsonResponse({"success": False, "error": "Supplier name is required"})

            # Auto-generate tracking number if not provided
            if not tracking:
                tracking = f"QUICK-{uuid.uuid4().hex[:8].upper()}"

            # Default expected date is 2 weeks from now
            expected_date = timezone.now().date() + timedelta(days=14)

            try:
                shipment = Shipment.objects.create(
                    tracking_number=tracking,
                    supplier=supplier,
                    expected_date=expected_date,
                    status="pending",
                )

                return JsonResponse({
                    "success": True,
                    "shipment": {
                        "id": shipment.id,
                        "name": shipment.name,
                        "tracking_number": shipment.tracking_number,
                        "supplier": shipment.supplier,
                        "expected_date": shipment.expected_date.isoformat(),
                        "status": shipment.status,
                    }
                })
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "add_variant_to_shipment":
            from decimal import Decimal

            from django.http import JsonResponse

            from shop.models import Shipment, ShipmentItem

            shipment_id = request.POST.get("shipment_id")
            variant_id = request.POST.get("variant_id")
            quantity = request.POST.get("quantity", 0)
            unit_cost = request.POST.get("unit_cost", "")

            if not shipment_id or not variant_id:
                return JsonResponse({"success": False, "error": "Shipment and variant are required"})

            try:
                quantity = int(quantity)
                if quantity <= 0:
                    return JsonResponse({"success": False, "error": "Quantity must be positive"})

                shipment = Shipment.objects.get(id=shipment_id)
                variant = ProductVariant.objects.select_related("product").get(id=variant_id)

                # Auto-populate unit_cost from variant cost or product base_cost if not provided
                if unit_cost and unit_cost.strip():
                    final_cost = Decimal(unit_cost)
                elif variant.cost is not None:
                    final_cost = variant.cost
                else:
                    final_cost = variant.product.base_cost or Decimal("0")

                # Check if item already exists - update quantity if so
                item, created = ShipmentItem.objects.get_or_create(
                    shipment=shipment,
                    variant=variant,
                    defaults={
                        "quantity": quantity,
                        "unit_cost": final_cost,
                    }
                )

                if not created:
                    # Update existing item
                    item.quantity += quantity
                    item.unit_cost = final_cost
                    item.save()

                return JsonResponse({
                    "success": True,
                    "created": created,
                    "item": {
                        "id": item.id,
                        "quantity": item.quantity,
                        "unit_cost": str(item.unit_cost),
                    }
                })
            except Shipment.DoesNotExist:
                return JsonResponse({"success": False, "error": "Shipment not found"})
            except ProductVariant.DoesNotExist:
                return JsonResponse({"success": False, "error": "Variant not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "bulk_update_stock":
            """
            Update stock for multiple variants at once.
            Supports setting absolute value or incrementing/decrementing.
            """
            import json

            from django.http import JsonResponse

            product_id = request.POST.get("product_id")
            update_mode = request.POST.get("update_mode", "set")  # 'set', 'add', 'subtract'
            stock_value = int(request.POST.get("stock_value", 0))
            variant_ids = request.POST.getlist("variant_ids[]") or json.loads(request.POST.get("variant_ids", "[]"))

            try:
                product = Product.objects.get(id=product_id)

                if not variant_ids:
                    # If no specific variants, update all variants of this product
                    variants = product.variants.all()
                else:
                    variants = ProductVariant.objects.filter(id__in=variant_ids, product=product)

                updated_count = 0
                for variant in variants:
                    if update_mode == "set":
                        variant.stock_quantity = max(0, stock_value)
                    elif update_mode == "add":
                        variant.stock_quantity = variant.stock_quantity + stock_value
                    elif update_mode == "subtract":
                        variant.stock_quantity = max(0, variant.stock_quantity - stock_value)
                    variant.save()
                    updated_count += 1

                return JsonResponse({
                    "success": True,
                    "updated": updated_count,
                    "message": f"Updated stock for {updated_count} variant(s)"
                })
            except Product.DoesNotExist:
                return JsonResponse({"success": False, "error": "Product not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "delete_product":
            from django.http import JsonResponse

            product_id = request.POST.get("product_id")
            try:
                product = Product.objects.get(id=product_id)
                product_name = product.name
                # Delete all variants first (cascades automatically, but being explicit)
                product.variants.all().delete()
                product.delete()
                return JsonResponse({"success": True, "message": f'Product "{product_name}" deleted'})
            except Product.DoesNotExist:
                return JsonResponse({"success": False, "error": "Product not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        # If we got here, the action was not recognized
        return JsonResponse({"success": False, "error": f"Unknown action: {action}"})

    # Get sort parameter
    sort_by = request.GET.get("sort", "newest")

    # Import aggregation functions
    from django.db.models import Max, Min

    # Get all products with variant data in a single query (optimized)
    # Exclude test checkout item from inventory reports
    products = Product.objects.exclude(slug="test-checkout-item").select_related("category_obj").annotate(
        variants_count=Count("variants"),
        stock_total=Sum("variants__stock_quantity"),
        variants_active=Count("variants", filter=Q(variants__is_active=True)),
        min_price=Min("variants__price"),
        max_price=Max("variants__price"),
    )

    # Apply sorting
    if sort_by == "newest":
        products = products.order_by("-created_at")
    elif sort_by == "name":
        products = products.order_by("name")
    elif sort_by == "category":
        products = products.order_by("category_obj__name", "name")
    elif sort_by == "status":
        products = products.order_by("-is_active", "name")
    else:
        products = products.order_by("-created_at")

    # Build products data from annotated queryset
    products_data = []
    for product in products:
        # Format price range
        min_price = product.min_price
        max_price = product.max_price
        if min_price is None or max_price is None:
            price_range = f"${product.base_price:.2f}"
        elif min_price == max_price:
            price_range = f"${min_price:.2f}"
        else:
            price_range = f"${min_price:.2f} - ${max_price:.2f}"

        # Get category slug for editing
        category_slug = ""
        if product.category_obj:
            category_slug = product.category_obj.slug
        elif product.category_legacy:
            category_slug = product.category_legacy

        products_data.append(
            {
                "id": product.id,
                "name": product.name,
                "slug": product.slug,
                "category": (
                    product.category_obj.name
                    if product.category_obj
                    else (product.category_legacy or "Uncategorized")
                ),
                "category_slug": category_slug,
                "description": product.description,
                "base_price": product.base_price,
                "base_cost": product.base_cost,
                "price_range": price_range,
                "is_active": product.is_active,
                "featured": product.featured,
                "available_for_purchase": product.available_for_purchase,
                "variant_count": product.variants_count or 0,
                "total_stock": product.stock_total or 0,
                "active_variants": product.variants_active or 0,
                "images": product.images or [],
            }
        )

    # Stats - use already-fetched data to avoid extra queries
    total_products = len(products_data)
    active_products = sum(1 for p in products_data if p.get("is_active", True))

    # Get variant stats in a single query instead of 4 separate queries
    # Exclude test checkout item from stats
    variant_stats = ProductVariant.objects.exclude(product__slug="test-checkout-item").aggregate(
        total_variants=Count("id"),
        total_stock=Sum("stock_quantity"),
        low_stock_count=Count("id", filter=Q(stock_quantity__lt=10, stock_quantity__gt=0)),
        out_of_stock_count=Count("id", filter=Q(stock_quantity=0)),
    )
    total_variants = variant_stats["total_variants"] or 0
    total_stock = variant_stats["total_stock"] or 0
    low_stock_count = variant_stats["low_stock_count"] or 0
    out_of_stock_count = variant_stats["out_of_stock_count"] or 0

    # Get all categories for the dropdown
    from shop.models import Category

    categories = Category.objects.all().order_by("name")

    context = {
        "products": products_data,
        "categories": categories,
        "total_products": total_products,
        "active_products": active_products,
        "total_variants": total_variants,
        "total_stock": total_stock,
        "low_stock_count": low_stock_count,
        "out_of_stock_count": out_of_stock_count,
        "sort_by": sort_by,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/products_dashboard.html", context)


@staff_member_required
def product_wizard(request):
    """
    Step-by-step product creation wizard.
    Provides a simpler flow for creating products with variants.
    """
    from shop.models import Category, Color, CustomAttribute, Material, Size

    # Get all categories
    categories = Category.objects.all().order_by("name")

    # Get all standard attribute values
    sizes = Size.objects.all().order_by("code")
    colors = Color.objects.all().order_by("name")
    materials = Material.objects.all().order_by("name")

    # Get custom attributes with their values
    custom_attributes = CustomAttribute.objects.filter(is_active=True).prefetch_related("values").order_by("name")
    custom_attrs_data = []
    for attr in custom_attributes:
        custom_attrs_data.append({
            "id": attr.id,
            "name": attr.name,
            "slug": attr.slug,
            "values": list(attr.values.filter(is_active=True).order_by("display_order", "value").values("id", "value"))
        })

    context = {
        "categories": categories,
        "sizes": sizes,
        "colors": colors,
        "materials": materials,
        "custom_attributes": custom_attrs_data,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/product_wizard.html", context)


@staff_member_required
def product_preview(request, product_id):
    """
    Preview a product as it would appear to customers.
    """
    from shop.models import Product

    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return HttpResponse("Product not found", status=404)

    # Collect unique images from variants
    images = []
    seen_images = set()
    for variant in product.variants.all():
        if variant.images:
            for img in variant.images:
                if img and not img.startswith(("/", "http")):
                    img_path = f"/static/{img}"
                else:
                    img_path = img
                if img_path not in seen_images:
                    images.append(img_path)
                    seen_images.add(img_path)

    context = {
        "product": product,
        "images": images,
    }

    return render(request, "admin/product_preview.html", context)


@staff_member_required
def categories_dashboard(request):
    """
    Categories management dashboard.
    """
    from django.http import JsonResponse

    from shop.models import Category

    # Handle category actions
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create_category":
            import json

            try:
                name = request.POST.get("name")
                slug = request.POST.get("slug")
                description = request.POST.get("description", "")
                uses_size = request.POST.get("uses_size") == "true"
                uses_color = request.POST.get("uses_color") == "true"
                uses_material = request.POST.get("uses_material") == "true"
                custom_attributes = json.loads(request.POST.get("custom_attributes", "[]"))
                common_fields = json.loads(request.POST.get("common_fields", "[]"))

                category = Category.objects.create(
                    name=name,
                    slug=slug,
                    description=description,
                    uses_size=uses_size,
                    uses_color=uses_color,
                    uses_material=uses_material,
                    custom_attributes=custom_attributes,
                    common_fields=common_fields,
                )

                return JsonResponse({"success": True, "category_id": category.id})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_category":
            import json

            try:
                category_id = request.POST.get("category_id")
                category = Category.objects.get(id=category_id)

                category.name = request.POST.get("name")
                category.slug = request.POST.get("slug")
                category.description = request.POST.get("description", "")
                category.uses_size = request.POST.get("uses_size") == "true"
                category.uses_color = request.POST.get("uses_color") == "true"
                category.uses_material = request.POST.get("uses_material") == "true"
                category.custom_attributes = json.loads(request.POST.get("custom_attributes", "[]"))
                category.common_fields = json.loads(request.POST.get("common_fields", "[]"))
                category.save()

                return JsonResponse({"success": True})
            except Category.DoesNotExist:
                return JsonResponse({"success": False, "error": "Category not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "delete_category":
            try:
                category_id = request.POST.get("category_id")
                category = Category.objects.get(id=category_id)

                # Check if category has products
                if category.products.exists():
                    return JsonResponse(
                        {
                            "success": False,
                            "error": f"Cannot delete category with {category.products.count()} products. Reassign or delete products first.",
                        }
                    )

                category.delete()
                return JsonResponse({"success": True})
            except Category.DoesNotExist:
                return JsonResponse({"success": False, "error": "Category not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "toggle_category_visibility":
            try:
                category_id = request.POST.get("category_id")
                category = Category.objects.get(id=category_id)
                category.is_hidden = not category.is_hidden
                category.save()
                return JsonResponse({"success": True, "is_hidden": category.is_hidden})
            except Category.DoesNotExist:
                return JsonResponse({"success": False, "error": "Category not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

    # Get all categories with product counts
    categories = Category.objects.all().order_by("name")
    categories_data = []

    for category in categories:
        # Get all products in this category
        all_products = category.products.all()

        # Active products (is_active=True and has stock)
        active_count = 0
        # Out of stock (is_active=True but no stock)
        out_of_stock_count = 0
        # Draft/pending (is_active=False)
        draft_count = all_products.filter(is_active=False).count()

        for product in all_products.filter(is_active=True):
            total_stock = product.total_stock
            if total_stock > 0:
                active_count += 1
            else:
                out_of_stock_count += 1

        categories_data.append(
            {
                "id": category.id,
                "name": category.name,
                "slug": category.slug,
                "description": category.description,
                "uses_size": category.uses_size,
                "uses_color": category.uses_color,
                "uses_material": category.uses_material,
                "custom_attributes": category.custom_attributes,
                "common_fields": category.common_fields,
                "is_hidden": category.is_hidden,
                "product_count": category.products.count(),
                "active_count": active_count,
                "out_of_stock_count": out_of_stock_count,
                "draft_count": draft_count,
            }
        )

    import json

    context = {
        "categories": categories_data,
        "categories_json": json.dumps(categories_data),
        "total_categories": categories.count(),
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/categories_dashboard.html", context)


@staff_member_required
def promotions_dashboard(request):
    """
    Promotions and deals management dashboard.
    """
    from django.http import JsonResponse

    from shop.models import Discount

    # Handle discount actions
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "toggle_discount" or action == "toggle_discount_status":
            discount_id = request.POST.get("discount_id")
            try:
                discount = Discount.objects.get(id=discount_id)
                discount.is_active = not discount.is_active
                discount.save()
                return JsonResponse({"success": True, "is_active": discount.is_active})
            except Discount.DoesNotExist:
                return JsonResponse({"success": False, "error": "Discount not found"})

        elif action == "create_discount":
            try:
                discount = Discount(
                    name=request.POST.get("name"),
                    code=request.POST.get("code"),
                    discount_type=request.POST.get("discount_type"),
                    value=request.POST.get("value"),
                    min_purchase_amount=request.POST.get("min_purchase_amount") or None,
                    max_uses=request.POST.get("max_uses") or None,
                    valid_from=request.POST.get("valid_from"),
                    valid_until=request.POST.get("valid_until") or None,
                    applies_to_all=request.POST.get("applies_to_all") == "on",
                    is_active=request.POST.get("is_active") == "on",
                    link_destination=request.POST.get("link_destination", ""),
                    landing_url=request.POST.get("landing_url", ""),
                )
                discount.save()
                messages.success(request, f"Promotion '{discount.name}' created successfully!")
                return redirect("promotions_dashboard")
            except Exception as e:
                messages.error(request, f"Error creating promotion: {str(e)}")
                return redirect("promotions_dashboard")

        elif action == "update_discount":
            try:
                discount_id = request.POST.get("discount_id")
                discount = Discount.objects.get(id=discount_id)

                discount.name = request.POST.get("name")
                discount.code = request.POST.get("code", "")
                discount.discount_type = request.POST.get("discount_type")
                discount.value = request.POST.get("value")
                discount.valid_from = request.POST.get("valid_from")
                discount.valid_until = request.POST.get("valid_until") or None
                discount.min_purchase_amount = request.POST.get("min_purchase_amount") or None
                discount.max_uses = request.POST.get("max_uses") or None
                discount.applies_to_all = request.POST.get("applies_to_all") == "on"
                discount.is_active = request.POST.get("is_active") == "on"
                discount.link_destination = request.POST.get("link_destination", "")
                discount.landing_url = request.POST.get("landing_url", "")

                discount.save()
                messages.success(request, f"Promotion '{discount.name}' updated successfully!")
                return redirect("promotions_dashboard")
            except Discount.DoesNotExist:
                messages.error(request, "Promotion not found")
                return redirect("promotions_dashboard")
            except Exception as e:
                messages.error(request, f"Error updating promotion: {str(e)}")
                return redirect("promotions_dashboard")

    # Get all discounts
    discounts = Discount.objects.all().order_by("-created_at")

    # Stats
    active_discounts = discounts.filter(is_active=True).count()
    total_uses = sum(d.times_used for d in discounts)

    # Get valid discounts
    from django.utils import timezone

    now = timezone.now()
    valid_discounts = [d for d in discounts if d.is_valid]

    context = {
        "discounts": discounts,
        "active_discounts": active_discounts,
        "total_uses": total_uses,
        "valid_discounts_count": len(valid_discounts),
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/discounts_dashboard.html", context)


@staff_member_required
def attributes_dashboard(request):
    """
    Manage product attributes: Sizes, Colors, Materials, and Custom Attributes.
    These are used to create product variants.
    """
    from django.http import JsonResponse
    from django.utils.text import slugify

    from shop.models import Color, CustomAttribute, CustomAttributeValue, Material, Size

    # Handle AJAX actions
    if request.method == "POST":
        action = request.POST.get("action")

        # SIZE ACTIONS
        if action == "create_size":
            try:
                code = request.POST.get("code", "").strip().upper()
                label = request.POST.get("label", "").strip()
                if not code:
                    return JsonResponse({"success": False, "error": "Size code is required"})
                if Size.objects.filter(code=code).exists():
                    return JsonResponse({"success": False, "error": f"Size '{code}' already exists"})
                size = Size.objects.create(code=code, label=label or code)
                return JsonResponse({"success": True, "id": size.id, "code": size.code, "label": size.label})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_size":
            try:
                size_id = request.POST.get("size_id")
                code = request.POST.get("code", "").strip().upper()
                label = request.POST.get("label", "").strip()
                size = Size.objects.get(id=size_id)
                if code and code != size.code:
                    if Size.objects.filter(code=code).exclude(id=size_id).exists():
                        return JsonResponse({"success": False, "error": f"Size '{code}' already exists"})
                    size.code = code
                size.label = label or code
                size.save()
                return JsonResponse({"success": True})
            except Size.DoesNotExist:
                return JsonResponse({"success": False, "error": "Size not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "delete_size":
            try:
                size_id = request.POST.get("size_id")
                size = Size.objects.get(id=size_id)
                # Check if size is in use
                variant_count = size.productvariant_set.count()
                if variant_count > 0:
                    return JsonResponse({
                        "success": False,
                        "error": f"Cannot delete: {variant_count} variant(s) are using this size"
                    })
                size.delete()
                return JsonResponse({"success": True})
            except Size.DoesNotExist:
                return JsonResponse({"success": False, "error": "Size not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        # COLOR ACTIONS
        elif action == "create_color":
            try:
                name = request.POST.get("name", "").strip()
                if not name:
                    return JsonResponse({"success": False, "error": "Color name is required"})
                if Color.objects.filter(name__iexact=name).exists():
                    return JsonResponse({"success": False, "error": f"Color '{name}' already exists"})
                color = Color.objects.create(name=name)
                return JsonResponse({"success": True, "id": color.id, "name": color.name})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_color":
            try:
                color_id = request.POST.get("color_id")
                name = request.POST.get("name", "").strip()
                color = Color.objects.get(id=color_id)
                if name and name.lower() != color.name.lower():
                    if Color.objects.filter(name__iexact=name).exclude(id=color_id).exists():
                        return JsonResponse({"success": False, "error": f"Color '{name}' already exists"})
                    color.name = name
                    color.save()
                return JsonResponse({"success": True})
            except Color.DoesNotExist:
                return JsonResponse({"success": False, "error": "Color not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "delete_color":
            try:
                color_id = request.POST.get("color_id")
                color = Color.objects.get(id=color_id)
                variant_count = color.productvariant_set.count()
                if variant_count > 0:
                    return JsonResponse({
                        "success": False,
                        "error": f"Cannot delete: {variant_count} variant(s) are using this color"
                    })
                color.delete()
                return JsonResponse({"success": True})
            except Color.DoesNotExist:
                return JsonResponse({"success": False, "error": "Color not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        # MATERIAL ACTIONS
        elif action == "create_material":
            try:
                name = request.POST.get("name", "").strip()
                description = request.POST.get("description", "").strip()
                if not name:
                    return JsonResponse({"success": False, "error": "Material name is required"})
                if Material.objects.filter(name__iexact=name).exists():
                    return JsonResponse({"success": False, "error": f"Material '{name}' already exists"})
                material = Material.objects.create(name=name, description=description)
                return JsonResponse({"success": True, "id": material.id, "name": material.name})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_material":
            try:
                material_id = request.POST.get("material_id")
                name = request.POST.get("name", "").strip()
                description = request.POST.get("description", "").strip()
                material = Material.objects.get(id=material_id)
                if name and name.lower() != material.name.lower():
                    if Material.objects.filter(name__iexact=name).exclude(id=material_id).exists():
                        return JsonResponse({"success": False, "error": f"Material '{name}' already exists"})
                    material.name = name
                material.description = description
                material.save()
                return JsonResponse({"success": True})
            except Material.DoesNotExist:
                return JsonResponse({"success": False, "error": "Material not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "delete_material":
            try:
                material_id = request.POST.get("material_id")
                material = Material.objects.get(id=material_id)
                variant_count = material.productvariant_set.count()
                if variant_count > 0:
                    return JsonResponse({
                        "success": False,
                        "error": f"Cannot delete: {variant_count} variant(s) are using this material"
                    })
                material.delete()
                return JsonResponse({"success": True})
            except Material.DoesNotExist:
                return JsonResponse({"success": False, "error": "Material not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        # CUSTOM ATTRIBUTE ACTIONS
        elif action == "create_custom_attribute":
            try:
                from django.db.models import Max

                name = request.POST.get("name", "").strip()
                input_type = request.POST.get("input_type", "select").strip()
                description = request.POST.get("description", "").strip()
                if not name:
                    return JsonResponse({"success": False, "error": "Attribute name is required"})
                slug = slugify(name)
                if CustomAttribute.objects.filter(slug=slug).exists():
                    return JsonResponse({"success": False, "error": f"Attribute '{name}' already exists"})
                # Get next display order
                max_order = CustomAttribute.objects.aggregate(Max("display_order"))["display_order__max"] or 0
                attr = CustomAttribute.objects.create(
                    name=name, slug=slug, input_type=input_type,
                    description=description, display_order=max_order + 1
                )
                return JsonResponse({"success": True, "id": attr.id, "name": attr.name, "slug": attr.slug})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_custom_attribute":
            try:
                attr_id = request.POST.get("attribute_id")
                name = request.POST.get("name", "").strip()
                description = request.POST.get("description", "").strip()
                attr = CustomAttribute.objects.get(id=attr_id)
                if name and name != attr.name:
                    new_slug = slugify(name)
                    if CustomAttribute.objects.filter(slug=new_slug).exclude(id=attr_id).exists():
                        return JsonResponse({"success": False, "error": f"Attribute '{name}' already exists"})
                    attr.name = name
                    attr.slug = new_slug
                attr.description = description
                attr.save()
                return JsonResponse({"success": True})
            except CustomAttribute.DoesNotExist:
                return JsonResponse({"success": False, "error": "Attribute not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "delete_custom_attribute":
            try:
                attr_id = request.POST.get("attribute_id")
                attr = CustomAttribute.objects.get(id=attr_id)
                # Check if any values are linked to product variants
                in_use_count = sum(v.variants.count() for v in attr.values.all())
                if in_use_count > 0:
                    return JsonResponse({
                        "success": False,
                        "error": f"Cannot delete '{attr.name}' - it has values linked to {in_use_count} product variant(s). Remove from products first."
                    })
                value_count = attr.values.count()
                attr.delete()
                return JsonResponse({"success": True, "values_deleted": value_count})
            except CustomAttribute.DoesNotExist:
                return JsonResponse({"success": False, "error": "Attribute not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        # CUSTOM ATTRIBUTE VALUE ACTIONS
        elif action == "add_attribute_value":
            try:
                from django.db.models import Max

                attr_id = request.POST.get("attribute_id")
                value = request.POST.get("value", "").strip()
                hex_code = request.POST.get("hex_code", "").strip()
                if not value:
                    return JsonResponse({"success": False, "error": "Value is required"})
                attr = CustomAttribute.objects.get(id=attr_id)
                if attr.values.filter(value__iexact=value).exists():
                    return JsonResponse({"success": False, "error": f"Value '{value}' already exists"})
                # Get next display order
                max_order = attr.values.aggregate(Max("display_order"))["display_order__max"] or 0
                # Build metadata if hex_code provided
                metadata = {}
                if hex_code:
                    metadata["hex_code"] = hex_code
                attr_value = CustomAttributeValue.objects.create(
                    attribute=attr, value=value, display_order=max_order + 1, metadata=metadata
                )
                return JsonResponse({"success": True, "id": attr_value.id, "value": attr_value.value})
            except CustomAttribute.DoesNotExist:
                return JsonResponse({"success": False, "error": "Attribute not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "delete_attribute_value":
            try:
                value_id = request.POST.get("value_id")
                attr_value = CustomAttributeValue.objects.get(id=value_id)
                # Check if value is linked to any product variants
                variant_count = attr_value.variants.count()
                if variant_count > 0:
                    return JsonResponse({
                        "success": False,
                        "error": f"Cannot delete '{attr_value.value}' - it's linked to {variant_count} product variant(s)."
                    })
                attr_value.delete()
                return JsonResponse({"success": True})
            except CustomAttributeValue.DoesNotExist:
                return JsonResponse({"success": False, "error": "Value not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "reorder_attribute_values":
            # Reorder values within an attribute (drag-and-drop)
            try:
                import json
                value_ids = json.loads(request.POST.get("value_ids", "[]"))
                for order, value_id in enumerate(value_ids):
                    CustomAttributeValue.objects.filter(id=value_id).update(display_order=order)
                return JsonResponse({"success": True})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_attribute_value":
            # Update a value's metadata (e.g., hex_code for colors)
            try:
                import json
                value_id = request.POST.get("value_id")
                attr_value = CustomAttributeValue.objects.get(id=value_id)

                # Update metadata
                metadata = attr_value.metadata or {}
                hex_code = request.POST.get("hex_code")
                label = request.POST.get("label")

                if hex_code is not None:
                    metadata["hex_code"] = hex_code
                if label is not None:
                    metadata["label"] = label

                attr_value.metadata = metadata
                attr_value.save()
                return JsonResponse({"success": True, "metadata": metadata})
            except CustomAttributeValue.DoesNotExist:
                return JsonResponse({"success": False, "error": "Value not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_attribute_type":
            # Update an attribute's input_type and display_order
            try:
                attr_id = request.POST.get("attribute_id")
                attr = CustomAttribute.objects.get(id=attr_id)

                input_type = request.POST.get("input_type")
                display_order = request.POST.get("display_order")

                if input_type:
                    attr.input_type = input_type
                if display_order is not None:
                    attr.display_order = int(display_order)

                attr.save()
                return JsonResponse({"success": True})
            except CustomAttribute.DoesNotExist:
                return JsonResponse({"success": False, "error": "Attribute not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "reorder_attributes":
            # Reorder attributes (drag-and-drop)
            try:
                import json
                attr_ids = json.loads(request.POST.get("attribute_ids", "[]"))
                for order, attr_id in enumerate(attr_ids):
                    CustomAttribute.objects.filter(id=attr_id).update(display_order=order)
                return JsonResponse({"success": True})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

    # GET request - render dashboard
    sizes = Size.objects.all().order_by("code")
    colors = Color.objects.all().order_by("name")
    materials = Material.objects.all().order_by("name")

    # Get usage counts
    sizes_data = []
    for size in sizes:
        variant_count = size.productvariant_set.count()
        sizes_data.append({
            "id": size.id,
            "code": size.code,
            "label": size.label,
            "variant_count": variant_count,
        })

    colors_data = []
    for color in colors:
        variant_count = color.productvariant_set.count()
        colors_data.append({
            "id": color.id,
            "name": color.name,
            "variant_count": variant_count,
        })

    materials_data = []
    for material in materials:
        variant_count = material.productvariant_set.count()
        materials_data.append({
            "id": material.id,
            "name": material.name,
            "description": material.description,
            "variant_count": variant_count,
        })

    # Get custom attributes with their values, ordered by display_order
    custom_attributes = CustomAttribute.objects.prefetch_related("values").filter(is_active=True).order_by("display_order", "name")
    custom_attrs_data = []
    total_values = 0
    total_in_use = 0
    for attr in custom_attributes:
        values_data = []
        for v in attr.values.filter(is_active=True).order_by("display_order", "value"):
            # Count variants using this value
            variant_count = v.variants.count()
            values_data.append({
                "id": v.id,
                "value": v.value,
                "display_order": v.display_order,
                "metadata": v.metadata or {},
                "variant_count": variant_count,
            })
            total_values += 1
            if variant_count > 0:
                total_in_use += 1
        custom_attrs_data.append({
            "id": attr.id,
            "name": attr.name,
            "input_type": attr.input_type,
            "display_order": attr.display_order,
            "slug": attr.slug,
            "description": attr.description,
            "values": values_data,
            "value_count": len(values_data),
        })

    context = {
        "sizes": sizes_data,
        "colors": colors_data,
        "materials": materials_data,
        "custom_attributes": custom_attrs_data,
        "total_sizes": len(sizes_data),
        "total_colors": len(colors_data),
        "total_materials": len(materials_data),
        "total_custom_attributes": len(custom_attrs_data),
        "total_values": total_values,
        "total_in_use": total_in_use,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/attributes_dashboard.html", context)


@staff_member_required
def messages_dashboard(request):
    """
    Dashboard showing all quick messages sent from the admin.
    """
    from .models.messaging import QuickMessage
    from .models.settings import SiteSettings

    # Handle POST request for saving test settings
    if request.method == "POST" and request.POST.get("action") == "save_test_settings":
        from django.http import JsonResponse

        try:
            settings = SiteSettings.load()
            settings.default_test_email = request.POST.get("test_email", "").strip()
            settings.default_test_phone = request.POST.get("test_phone", "").strip()
            settings.save()
            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    # Handle cancel scheduled message
    if request.method == "POST" and request.POST.get("action") == "cancel_scheduled":
        from django.http import JsonResponse

        try:
            message_id = request.POST.get("message_id")
            message = QuickMessage.objects.get(id=message_id, status="scheduled")
            message.delete()
            return JsonResponse({"success": True})
        except QuickMessage.DoesNotExist:
            return JsonResponse({"success": False, "error": "Message not found"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    # Handle save draft
    if request.method == "POST" and request.POST.get("action") == "save_draft":
        from django.http import JsonResponse

        message_type = request.POST.get("message_type", "email")
        subject = request.POST.get("subject", "")
        content = request.POST.get("content", "")
        draft_id = request.POST.get("draft_id")
        scheduled_for_str = request.POST.get("scheduled_for", "").strip()

        # Parse scheduled_for if provided
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
                # Update existing draft
                draft = QuickMessage.objects.get(id=draft_id, status="draft")
                draft.message_type = message_type
                draft.subject = subject
                draft.content = content
                draft.scheduled_for = scheduled_for
                draft.save()
            else:
                # Create new draft
                draft = QuickMessage.objects.create(
                    message_type=message_type,
                    subject=subject,
                    content=content,
                    status="draft",
                    scheduled_for=scheduled_for,
                )
            return JsonResponse({"success": True, "draft_id": draft.id})
        except QuickMessage.DoesNotExist:
            return JsonResponse({"success": False, "error": "Draft not found"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    # Get filter parameters
    message_type = request.GET.get("type", "all")
    date_range = request.GET.get("range", "30")

    # Base queryset - exclude drafts from main list
    messages = QuickMessage.objects.exclude(status="draft").order_by("-created_at")

    # Apply filters
    if message_type in ["email", "sms"]:
        messages = messages.filter(message_type=message_type)

    if date_range != "all":
        try:
            days = int(date_range)
            cutoff = timezone.now() - timedelta(days=days)
            messages = messages.filter(created_at__gte=cutoff)
        except ValueError:
            pass

    # Get drafts separately
    drafts = QuickMessage.objects.filter(status="draft").order_by("-updated_at")

    # Get scheduled messages separately
    scheduled_messages = QuickMessage.objects.filter(status="scheduled").order_by("scheduled_for")

    # Build timeline: combine scheduled messages + drafts with scheduled times + recently sent
    timeline_items = []

    # Add scheduled messages to timeline (pending)
    for msg in scheduled_messages:
        timeline_items.append({
            "id": msg.id,
            "type": "scheduled",
            "status": "pending",
            "message_type": msg.message_type,
            "subject": msg.subject,
            "content": msg.content,
            "scheduled_for": msg.scheduled_for,
            "sent_at": None,
            "recipient_count": msg.recipient_count,
            "sent_count": 0,
            "failed_count": 0,
        })

    # Add drafts with future scheduled times to timeline (skip past times)
    now = timezone.now()
    for draft in drafts.filter(scheduled_for__isnull=False, scheduled_for__gt=now):
        timeline_items.append({
            "id": draft.id,
            "type": "draft",
            "status": "draft",
            "message_type": draft.message_type,
            "subject": draft.subject,
            "content": draft.content,
            "scheduled_for": draft.scheduled_for,
            "sent_at": None,
            "recipient_count": 0,
            "sent_count": 0,
            "failed_count": 0,
        })

    # Sort by scheduled_for time
    timeline_items.sort(key=lambda x: x["scheduled_for"])

    # Calculate stats (exclude drafts and scheduled)
    sent_messages = QuickMessage.objects.exclude(status__in=["draft", "scheduled"])
    total_messages = sent_messages.count()
    total_sent = sent_messages.aggregate(total=Sum("sent_count"))["total"] or 0
    total_failed = sent_messages.aggregate(total=Sum("failed_count"))["total"] or 0
    email_messages = sent_messages.filter(message_type="email").count()
    sms_messages = sent_messages.filter(message_type="sms").count()
    draft_count = drafts.count()
    scheduled_count = scheduled_messages.count()

    # Get site settings for test defaults
    site_settings = SiteSettings.load()

    # Get subscriber counts for quick send form
    email_sub_count = EmailSubscription.objects.filter(is_active=True).count()
    sms_sub_count = SMSSubscription.objects.filter(is_active=True).count()

    context = {
        "messages": messages[:100],  # Limit to 100 most recent
        "drafts": drafts,
        "scheduled_messages": scheduled_messages,
        "timeline_items": timeline_items,
        "message_type": message_type,
        "date_range": date_range,
        "stats": {
            "total_messages": total_messages,
            "total_sent": total_sent,
            "total_failed": total_failed,
            "email_messages": email_messages,
            "sms_messages": sms_messages,
            "draft_count": draft_count,
            "scheduled_count": scheduled_count,
            "email_sub_count": email_sub_count,
            "sms_sub_count": sms_sub_count,
        },
        "default_test_email": site_settings.default_test_email,
        "default_test_phone": site_settings.default_test_phone,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/messages_dashboard.html", context)


@staff_member_required
def campaigns_list(request):
    """
    List all unified campaigns.
    """
    # Handle GET request for fetching message data
    if request.method == "GET" and request.GET.get("action") == "get_message":
        from django.http import JsonResponse

        try:
            message_id = request.GET.get("message_id")
            message = CampaignMessage.objects.get(id=message_id)

            return JsonResponse(
                {
                    "success": True,
                    "message": {
                        "id": message.id,
                        "message_type": message.message_type,
                        "custom_subject": message.custom_subject or "",
                        "custom_content": message.custom_content or "",
                        "media_urls": message.media_urls or "",
                        "notes": message.notes or "",
                        "send_mode": message.send_mode or "auto",
                    },
                }
            )
        except CampaignMessage.DoesNotExist:
            return JsonResponse({"success": False, "error": "Message not found"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    if request.method == "POST":
        action = request.POST.get("action")
        campaign_id = request.POST.get("campaign_id")

        if action == "delete":
            try:
                campaign = Campaign.objects.get(id=campaign_id)
                campaign.delete()
                messages.success(request, "Campaign deleted successfully!")
            except Exception as e:
                messages.error(request, f"Error deleting campaign: {str(e)}")
            return redirect("admin_campaigns_list")

        elif action == "update_window":
            try:
                from django.http import JsonResponse

                campaign = Campaign.objects.get(id=campaign_id)

                active_from = request.POST.get("active_from")
                active_until = request.POST.get("active_until")

                campaign.active_from = active_from if active_from else None
                campaign.active_until = active_until if active_until else None
                campaign.save()

                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({"success": True})
                else:
                    messages.success(request, "Operating window updated successfully!")
                    return redirect("admin_campaigns_list")
            except Exception as e:
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({"success": False, "error": str(e)})
                else:
                    messages.error(request, f"Error updating operating window: {str(e)}")
                    return redirect("admin_campaigns_list")

        elif action == "add_message":
            try:
                from datetime import datetime

                from django.db.models import Max

                campaign = Campaign.objects.get(id=campaign_id)
                message_type = request.POST.get("message_type")
                scheduled_date_str = request.POST.get("scheduled_date")

                # Get next order number
                max_order_result = campaign.messages.aggregate(max_order=Max("order"))
                max_order = (
                    max_order_result["max_order"]
                    if max_order_result["max_order"] is not None
                    else 0
                )
                next_order = max_order + 1

                # Parse scheduled date and time if provided
                scheduled_date = None
                if scheduled_date_str:
                    try:
                        # Parse date string (format: YYYY-MM-DD)
                        scheduled_date = timezone.datetime.strptime(scheduled_date_str, "%Y-%m-%d")

                        # Add time component if provided
                        scheduled_time_str = request.POST.get("scheduled_time")
                        if scheduled_time_str:
                            try:
                                time_parts = scheduled_time_str.split(":")
                                scheduled_date = scheduled_date.replace(
                                    hour=int(time_parts[0]),
                                    minute=int(time_parts[1]) if len(time_parts) > 1 else 0,
                                )
                            except (ValueError, IndexError):
                                pass

                        scheduled_date = timezone.make_aware(scheduled_date)
                    except ValueError:
                        pass

                # Get universal send_mode (fallback to type-specific if not provided)
                send_mode = request.POST.get("send_mode", "auto")

                # Create message based on type
                if message_type == "email":
                    subject = request.POST.get("email_subject", "").strip()
                    body = request.POST.get("email_body", "").strip()
                    recipient_group = request.POST.get("email_recipient", "all")
                    # Use type-specific send_mode if provided, otherwise use universal
                    send_mode = request.POST.get("email_send_mode", send_mode)

                    if not subject or not body:
                        messages.error(request, "Email subject and body are required!")
                        return redirect("admin_campaigns_list")

                    # Map recipient group to display name
                    recipient_display = {
                        "all": "All Email Subscribers",
                        "new_customers": "New Customers (Last 30 days)",
                        "vip": "VIP Customers",
                        "inactive": "Inactive Customers",
                        "custom": "Custom Selection",
                    }.get(recipient_group, "All Email Subscribers")

                    # Set status based on send mode
                    msg_status = "draft" if send_mode == "draft" else "pending"

                    message = CampaignMessage.objects.create(
                        campaign=campaign,
                        message_type="email",
                        name=f"{subject} → {recipient_display}",
                        custom_subject=subject,
                        custom_content=body,
                        order=next_order,
                        status=msg_status,
                        send_mode=send_mode,
                        trigger_type="specific_date" if scheduled_date else "immediate",
                        scheduled_date=scheduled_date,
                    )

                    messages.success(
                        request,
                        f'Email message "{subject}" added to campaign for {recipient_display}!',
                    )

                elif message_type == "sms":
                    sms_message = request.POST.get("sms_message", "").strip()
                    recipient_group = request.POST.get("sms_to", "all")
                    # Use type-specific send_mode if provided, otherwise use universal
                    send_mode = request.POST.get("sms_send_mode", send_mode)

                    if not sms_message:
                        messages.error(request, "SMS message is required!")
                        return redirect("admin_campaigns_list")

                    # Map recipient group to display name
                    recipient_display = {
                        "all": "All SMS Subscribers",
                        "new_customers": "New Customers (Last 30 days)",
                        "vip": "VIP Customers",
                        "inactive": "Inactive Customers",
                        "custom": "Custom Selection",
                    }.get(recipient_group, "All SMS Subscribers")

                    # Set status based on send mode
                    msg_status = "draft" if send_mode == "draft" else "pending"

                    message = CampaignMessage.objects.create(
                        campaign=campaign,
                        message_type="sms",
                        name=(
                            f"{sms_message[:30]}... → {recipient_display}"
                            if len(sms_message) > 30
                            else f"{sms_message} → {recipient_display}"
                        ),
                        custom_content=sms_message,
                        order=next_order,
                        status=msg_status,
                        send_mode=send_mode,
                        trigger_type="specific_date" if scheduled_date else "immediate",
                        scheduled_date=scheduled_date,
                    )

                    messages.success(
                        request, f"SMS message added to campaign for {recipient_display}!"
                    )

                elif message_type == "instagram":
                    caption = request.POST.get("instagram_caption", "").strip()
                    media_urls = request.POST.get("instagram_media", "").strip()
                    notes = request.POST.get("instagram_notes", "").strip()

                    # Set status based on send mode
                    msg_status = "draft" if send_mode == "draft" else "pending"

                    message = CampaignMessage.objects.create(
                        campaign=campaign,
                        message_type="instagram",
                        name=(
                            f"Instagram: {caption[:40]}..."
                            if len(caption) > 40
                            else f"Instagram: {caption}" if caption else "Instagram Post"
                        ),
                        custom_subject=caption,  # Caption
                        custom_content=notes,  # Notes
                        media_urls=media_urls,
                        notes=notes,
                        order=next_order,
                        status=msg_status,
                        send_mode=send_mode,
                        trigger_type="specific_date" if scheduled_date else "immediate",
                        scheduled_date=scheduled_date,
                    )

                    messages.success(request, "Instagram post added to campaign!")

                elif message_type == "tiktok":
                    caption = request.POST.get("tiktok_caption", "").strip()
                    media_url = request.POST.get("tiktok_media", "").strip()
                    notes = request.POST.get("tiktok_notes", "").strip()

                    message = CampaignMessage.objects.create(
                        campaign=campaign,
                        message_type="tiktok",
                        name=(
                            f"TikTok: {caption[:40]}..."
                            if len(caption) > 40
                            else f"TikTok: {caption}" if caption else "TikTok Video"
                        ),
                        custom_subject=caption,
                        custom_content=notes,
                        media_urls=media_url,
                        notes=notes,
                        order=next_order,
                        status="draft",
                        trigger_type="specific_date" if scheduled_date else "immediate",
                        scheduled_date=scheduled_date,
                    )

                    messages.success(request, "TikTok video added to campaign!")

                elif message_type == "snapchat":
                    caption = request.POST.get("snapchat_caption", "").strip()
                    media_url = request.POST.get("snapchat_media", "").strip()
                    notes = request.POST.get("snapchat_notes", "").strip()

                    message = CampaignMessage.objects.create(
                        campaign=campaign,
                        message_type="snapchat",
                        name=(
                            f"Snapchat: {caption[:40]}..."
                            if len(caption) > 40
                            else f"Snapchat: {caption}" if caption else "Snapchat Story"
                        ),
                        custom_subject=caption,
                        custom_content=notes,
                        media_urls=media_url,
                        notes=notes,
                        order=next_order,
                        status="draft",
                        trigger_type="specific_date" if scheduled_date else "immediate",
                        scheduled_date=scheduled_date,
                    )

                    messages.success(request, "Snapchat story added to campaign!")

                elif message_type == "youtube":
                    title = request.POST.get("youtube_title", "").strip()
                    video_url = request.POST.get("youtube_url", "").strip()
                    description = request.POST.get("youtube_description", "").strip()

                    message = CampaignMessage.objects.create(
                        campaign=campaign,
                        message_type="youtube",
                        name=(
                            f"YouTube: {title[:40]}..."
                            if len(title) > 40
                            else f"YouTube: {title}" if title else "YouTube Video"
                        ),
                        custom_subject=title,
                        custom_content=description,
                        media_urls=video_url,
                        notes=description,
                        order=next_order,
                        status="draft",
                        trigger_type="specific_date" if scheduled_date else "immediate",
                        scheduled_date=scheduled_date,
                    )

                    messages.success(request, "YouTube video added to campaign!")

                elif message_type == "promotion":
                    from decimal import Decimal

                    from shop.models import Discount, Product

                    promo_title = request.POST.get("promotion_title", "").strip()
                    promo_type = request.POST.get("promotion_type", "public").strip()
                    promo_code = request.POST.get("promotion_code", "").strip().upper()
                    discount_type = request.POST.get(
                        "promotion_discount_type", "percentage"
                    ).strip()
                    discount_value = request.POST.get("promotion_discount_value", "").strip()
                    product_ids = request.POST.getlist("promotion_products")
                    promo_details = request.POST.get("promotion_details", "").strip()

                    if not promo_title:
                        messages.error(request, "Promotion title is required!")
                        return redirect("admin_campaigns_list")

                    # Validate discount amount for all promotions (except BOGO and Free Shipping)
                    if discount_type not in ["bogo", "free_shipping"] and not discount_value:
                        messages.error(request, "Discount amount is required!")
                        return redirect("admin_campaigns_list")

                    # Validate private promotion requirements
                    if promo_type == "private":
                        if not promo_code:
                            messages.error(
                                request, "Discount code is required for private promotions!"
                            )
                            return redirect("admin_campaigns_list")

                        # Check code uniqueness
                        if Discount.objects.filter(code=promo_code).exists():
                            messages.error(
                                request,
                                f'Discount code "{promo_code}" already exists! Please use a different code.',
                            )
                            return redirect("admin_campaigns_list")

                    # Build notes with promotion type and code info
                    notes_parts = []
                    if promo_type == "public":
                        notes_parts.append("Type: Public Sale (No code required)")
                    else:
                        notes_parts.append("Type: Private/Code Only")
                        if promo_code:
                            notes_parts.append(f"Code: {promo_code}")

                    if promo_details:
                        notes_parts.append(f"\nDetails: {promo_details}")

                    combined_notes = "\n".join(notes_parts)

                    # Create the message
                    message = CampaignMessage.objects.create(
                        campaign=campaign,
                        message_type="promotion",
                        name=(
                            f"Promo: {promo_title[:40]}..."
                            if len(promo_title) > 40
                            else f"Promo: {promo_title}"
                        ),
                        custom_subject=promo_title,
                        custom_content=promo_details,
                        notes=combined_notes,
                        order=next_order,
                        status="draft",
                        trigger_type="specific_date" if scheduled_date else "immediate",
                        scheduled_date=scheduled_date,
                    )

                    # Create discount for all promotions
                    try:
                        # For BOGO, use 50 as the value (50% off second item is standard)
                        # For Free Shipping, use 0 (just a flag, actual shipping cost calculated at checkout)
                        if discount_type == "bogo":
                            discount_value = "50"
                        elif discount_type == "free_shipping":
                            discount_value = "0"

                        if discount_value:
                            # Generate a code for public promotions if not provided
                            if not promo_code:
                                # Auto-generate code for public sales (e.g., PUBLIC_SALE_12345)
                                import random

                                promo_code = f"AUTO_{random.randint(10000, 99999)}"

                            discount = Discount.objects.create(
                                name=promo_title,
                                code=promo_code,
                                discount_type=discount_type,
                                value=Decimal(discount_value),
                                valid_from=timezone.now(),
                                is_active=True,
                                applies_to_all=False if product_ids else True,
                            )
                            # Link products to discount if specified
                            if product_ids:
                                products_for_discount = Product.objects.filter(id__in=product_ids)
                                discount.products.set(products_for_discount)

                            message.discount = discount
                            message.save()
                    except Exception as e:
                        messages.error(request, f"Error creating discount: {str(e)}")
                        return redirect("admin_campaigns_list")

                    # Link products to message if selected
                    if product_ids:
                        products = Product.objects.filter(id__in=product_ids)
                        message.products.set(products)

                    success_msg = f"{'Public sale' if promo_type == 'public' else 'Private promotion'} added to campaign!"
                    if promo_code:
                        success_msg += f" Code: {promo_code}"
                    messages.success(request, success_msg)

                elif message_type == "product":
                    from shop.models import Product, ProductVariant

                    product_variant = request.POST.get("product_variant", "").strip()
                    announcement_title = request.POST.get("product_announcement_title", "").strip()
                    announcement_details = request.POST.get(
                        "product_announcement_details", ""
                    ).strip()
                    media_url = request.POST.get("product_media_url", "").strip()
                    release_time = request.POST.get("product_release_time", "09:00").strip()

                    if not product_variant:
                        messages.error(request, "Product or variant selection is required!")
                        return redirect("admin_campaigns_list")

                    # Parse product_variant (format: "product_123" or "variant_456")
                    product_name = ""
                    selected_products = []
                    if product_variant.startswith("product_"):
                        product_id = product_variant.replace("product_", "")
                        try:
                            product = Product.objects.get(id=product_id)
                            product_name = f"{product.name} (All Variants)"
                            selected_products = [product]
                        except Product.DoesNotExist:
                            messages.error(request, "Selected product not found!")
                            return redirect("admin_campaigns_list")
                    elif product_variant.startswith("variant_"):
                        variant_id = product_variant.replace("variant_", "")
                        try:
                            variant = ProductVariant.objects.get(id=variant_id)
                            product_name = f"{variant.product.name} - {variant.name}"
                            selected_products = [variant.product]
                        except ProductVariant.DoesNotExist:
                            messages.error(request, "Selected variant not found!")
                            return redirect("admin_campaigns_list")

                    # Build message name and notes
                    name = (
                        announcement_title
                        if announcement_title
                        else f"Product Release: {product_name}"
                    )
                    notes = f"Product: {product_name}\nRelease Time: {release_time}"
                    if announcement_details:
                        notes += f"\nDetails: {announcement_details}"

                    # Combine scheduled date with release time if provided
                    product_scheduled_date = scheduled_date
                    if scheduled_date and release_time:
                        try:
                            time_parts = release_time.split(":")
                            product_scheduled_date = scheduled_date.replace(
                                hour=int(time_parts[0]),
                                minute=int(time_parts[1]) if len(time_parts) > 1 else 0,
                            )
                        except (ValueError, IndexError):
                            pass

                    message = CampaignMessage.objects.create(
                        campaign=campaign,
                        message_type="product",
                        name=name,
                        custom_subject=announcement_title,
                        custom_content=announcement_details,
                        media_urls=media_url,
                        notes=notes,
                        order=next_order,
                        status="draft",
                        trigger_type="specific_date" if product_scheduled_date else "immediate",
                        scheduled_date=product_scheduled_date,
                    )

                    # Link products to message
                    if selected_products:
                        message.products.set(selected_products)

                    messages.success(request, f'Product release "{name}" added to campaign!')

                return redirect("admin_campaigns_list")
            except Campaign.DoesNotExist:
                messages.error(request, "Campaign not found!")
                return redirect("admin_campaigns_list")
            except Exception as e:
                messages.error(request, f"Error adding message: {str(e)}")
                return redirect("admin_campaigns_list")

        elif action == "update_message_date":
            try:
                from django.http import JsonResponse

                message_id = request.POST.get("message_id")
                scheduled_date_str = request.POST.get("scheduled_date")

                message = CampaignMessage.objects.get(id=message_id)

                # Parse scheduled date
                if scheduled_date_str:
                    try:
                        # Parse date string (format: YYYY-MM-DD)
                        scheduled_date = timezone.datetime.strptime(scheduled_date_str, "%Y-%m-%d")
                        scheduled_date = timezone.make_aware(scheduled_date)
                        message.scheduled_date = scheduled_date
                        message.trigger_type = "specific_date"
                        message.save()

                        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                            return JsonResponse({"success": True})
                        else:
                            messages.success(request, "Message date updated successfully!")
                            return redirect("admin_campaigns_list")
                    except ValueError as e:
                        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                            return JsonResponse(
                                {"success": False, "error": f"Invalid date format: {str(e)}"}
                            )
                        else:
                            messages.error(request, f"Invalid date format: {str(e)}")
                            return redirect("admin_campaigns_list")
                else:
                    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                        return JsonResponse({"success": False, "error": "No date provided"})
                    else:
                        messages.error(request, "No date provided")
                        return redirect("admin_campaigns_list")
            except CampaignMessage.DoesNotExist:
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({"success": False, "error": "Message not found"})
                else:
                    messages.error(request, "Message not found!")
                    return redirect("admin_campaigns_list")
            except Exception as e:
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({"success": False, "error": str(e)})
                else:
                    messages.error(request, f"Error updating message date: {str(e)}")
                    return redirect("admin_campaigns_list")

        elif action == "edit_message":
            try:
                from django.http import JsonResponse

                message_id = request.POST.get("message_id")
                message = CampaignMessage.objects.get(id=message_id)
                message_type = message.message_type

                # Update based on message type
                if message_type == "email":
                    message.custom_subject = request.POST.get("email_subject", "").strip()
                    message.custom_content = request.POST.get("email_body", "").strip()
                    message.send_mode = request.POST.get("email_send_mode", "auto")
                    message.status = "draft" if message.send_mode == "draft" else message.status
                elif message_type == "sms":
                    message.custom_content = request.POST.get("sms_message", "").strip()
                    message.send_mode = request.POST.get("sms_send_mode", "auto")
                    message.status = "draft" if message.send_mode == "draft" else message.status
                elif message_type == "instagram":
                    message.custom_subject = request.POST.get("instagram_caption", "").strip()
                    message.media_urls = request.POST.get("instagram_media", "").strip()
                    message.notes = request.POST.get("instagram_notes", "").strip()
                    message.custom_content = message.notes
                elif message_type == "tiktok":
                    message.custom_subject = request.POST.get("tiktok_caption", "").strip()
                    message.media_urls = request.POST.get("tiktok_media", "").strip()
                    message.notes = request.POST.get("tiktok_notes", "").strip()
                    message.custom_content = message.notes
                elif message_type == "snapchat":
                    message.custom_subject = request.POST.get("snapchat_caption", "").strip()
                    message.media_urls = request.POST.get("snapchat_media", "").strip()
                    message.notes = request.POST.get("snapchat_notes", "").strip()
                    message.custom_content = message.notes
                elif message_type == "youtube":
                    message.custom_subject = request.POST.get("youtube_title", "").strip()
                    message.media_urls = request.POST.get("youtube_url", "").strip()
                    message.notes = request.POST.get("youtube_description", "").strip()
                    message.custom_content = message.notes
                elif message_type == "promotion":
                    from shop.models import Discount, Product

                    promo_title = request.POST.get("promotion_title", "").strip()
                    promo_type = request.POST.get("promotion_type", "public").strip()
                    promo_code = request.POST.get("promotion_code", "").strip()
                    promo_details = request.POST.get("promotion_details", "").strip()

                    message.custom_subject = promo_title
                    message.custom_content = promo_details

                    # Build notes with promotion type and code info
                    notes_parts = []
                    if promo_type == "public":
                        notes_parts.append("Type: Public Sale (No code required)")
                    else:
                        notes_parts.append("Type: Private/Code Only")
                        if promo_code:
                            notes_parts.append(f"Code: {promo_code}")

                    if promo_details:
                        notes_parts.append(f"\nDetails: {promo_details}")

                    message.notes = "\n".join(notes_parts)

                    # Update discount if changed
                    discount_id = request.POST.get("promotion_discount", "").strip()
                    if discount_id:
                        try:
                            discount = Discount.objects.get(id=discount_id)
                            message.discount = discount
                        except Discount.DoesNotExist:
                            message.discount = None
                    else:
                        message.discount = None

                    # Update products if changed
                    product_ids = request.POST.getlist("promotion_products")
                    if product_ids:
                        products = Product.objects.filter(id__in=product_ids)
                        message.products.set(products)
                    else:
                        message.products.clear()

                message.save()

                messages.success(request, "Message updated successfully!")
                return redirect("admin_campaigns_list")
            except CampaignMessage.DoesNotExist:
                messages.error(request, "Message not found!")
                return redirect("admin_campaigns_list")
            except Exception as e:
                messages.error(request, f"Error updating message: {str(e)}")
                return redirect("admin_campaigns_list")

        elif action == "delete_message":
            try:
                from django.http import JsonResponse

                message_id = request.POST.get("message_id")
                message = CampaignMessage.objects.get(id=message_id)
                message.delete()

                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({"success": True})
                else:
                    messages.success(request, "Message deleted successfully!")
                    return redirect("admin_campaigns_list")
            except CampaignMessage.DoesNotExist:
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({"success": False, "error": "Message not found"})
                else:
                    messages.error(request, "Message not found!")
                    return redirect("admin_campaigns_list")
            except Exception as e:
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({"success": False, "error": str(e)})
                else:
                    messages.error(request, f"Error deleting message: {str(e)}")
                    return redirect("admin_campaigns_list")

        elif action == "change_message_status":
            try:
                from django.http import JsonResponse

                message_id = request.POST.get("message_id")
                new_status = request.POST.get("status")

                message = CampaignMessage.objects.get(id=message_id)
                message.status = new_status

                # Update sent_at if status is changed to 'sent'
                if new_status == "sent" and not message.sent_at:
                    message.sent_at = timezone.now()

                message.save()

                return JsonResponse({"success": True})
            except CampaignMessage.DoesNotExist:
                return JsonResponse({"success": False, "error": "Message not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "change_campaign_status":
            try:
                from django.http import JsonResponse

                campaign_id = request.POST.get("campaign_id")
                new_status = request.POST.get("status")

                campaign = Campaign.objects.get(id=campaign_id)
                campaign.status = new_status

                # Update started_at if status is changed to 'active' and not set
                if new_status == "active" and not campaign.started_at:
                    campaign.started_at = timezone.now()

                # Update completed_at if status is changed to 'completed'
                if new_status == "completed" and not campaign.completed_at:
                    campaign.completed_at = timezone.now()

                campaign.save()

                return JsonResponse({"success": True})
            except Campaign.DoesNotExist:
                return JsonResponse({"success": False, "error": "Campaign not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

    from django.db.models import Count, Q

    campaigns_queryset = Campaign.objects.all().prefetch_related("messages").order_by("-created_at")
    now = timezone.now()

    # Build enriched campaign data
    campaigns = []
    for campaign in campaigns_queryset:
        # Get message counts
        total_messages = campaign.messages.count()
        sent_messages = campaign.messages.filter(status="sent").count()

        # Get message sequence ordered by order field
        message_sequence = list(
            campaign.messages.all()
            .order_by("order")
            .values("id", "message_type", "status", "name", "scheduled_date", "sent_at")
        )

        # Count messages by type
        email_count = sum(1 for m in message_sequence if m["message_type"] == "email")
        sms_count = sum(1 for m in message_sequence if m["message_type"] == "sms")
        instagram_count = sum(1 for m in message_sequence if m["message_type"] == "instagram")
        tiktok_count = sum(1 for m in message_sequence if m["message_type"] == "tiktok")
        snapchat_count = sum(1 for m in message_sequence if m["message_type"] == "snapchat")

        # Calculate progress percentage
        if total_messages > 0:
            progress_percentage = int((sent_messages / total_messages) * 100)
        else:
            progress_percentage = 0

        # Determine display status
        if campaign.active_from and campaign.active_until:
            if now < campaign.active_from:
                display_status = "upcoming"
            elif now > campaign.active_until:
                display_status = "completed"
            else:
                display_status = "active"
        elif campaign.active_from:
            if now >= campaign.active_from:
                display_status = "active"
            else:
                display_status = "upcoming"
        elif campaign.active_until:
            if now <= campaign.active_until:
                display_status = "active"
            else:
                display_status = "completed"
        else:
            display_status = "draft"

        # Create enriched campaign object
        campaign_data = {
            "id": campaign.id,
            "name": campaign.name,
            "description": campaign.description,
            "target_group": campaign.target_group,
            "active_from": campaign.active_from,
            "active_until": campaign.active_until,
            "created_at": campaign.created_at,
            "total_messages": total_messages,
            "sent_messages": sent_messages,
            "progress_percentage": progress_percentage,
            "display_status": display_status,
            "message_sequence": message_sequence,
            "email_count": email_count,
            "sms_count": sms_count,
            "instagram_count": instagram_count,
            "tiktok_count": tiktok_count,
            "snapchat_count": snapchat_count,
        }
        campaigns.append(campaign_data)

    # Calculate overview stats
    total_campaigns = len(campaigns)
    active_campaigns = sum(1 for c in campaigns if c["display_status"] == "active")
    upcoming_campaigns = sum(1 for c in campaigns if c["display_status"] == "upcoming")
    total_messages = sum(c["total_messages"] for c in campaigns)
    sent_messages = sum(c["sent_messages"] for c in campaigns)

    # Get timeline campaigns (upcoming and active, sorted by start date)
    timeline_campaigns = [c for c in campaigns if c["display_status"] in ["upcoming", "active"]]
    timeline_campaigns.sort(key=lambda c: c["active_from"] if c["active_from"] else timezone.now())

    # Get upcoming messages (not sent yet, across all campaigns)
    upcoming_messages = (
        CampaignMessage.objects.select_related("campaign")
        .exclude(status="sent")
        .order_by("scheduled_date", "created_at")[:20]
    )
    upcoming_messages_data = []
    for msg in upcoming_messages:
        upcoming_messages_data.append(
            {
                "id": msg.id,
                "name": msg.name,
                "message_type": msg.message_type,
                "campaign_name": msg.campaign.name,
                "campaign_id": msg.campaign.id,
                "status": msg.status,
                "scheduled_date": msg.scheduled_date,
                "created_at": msg.created_at,
                "custom_subject": msg.custom_subject,
            }
        )

    # Get recent messages across all campaigns (most recent 20 sent messages)
    recent_messages = (
        CampaignMessage.objects.select_related("campaign")
        .filter(status="sent")
        .order_by("-sent_at")[:20]
    )
    recent_messages_data = []
    for msg in recent_messages:
        recent_messages_data.append(
            {
                "id": msg.id,
                "name": msg.name,
                "message_type": msg.message_type,
                "campaign_name": msg.campaign.name,
                "campaign_id": msg.campaign.id,
                "status": msg.status,
                "scheduled_date": msg.scheduled_date,
                "sent_at": msg.sent_at,
                "created_at": msg.created_at,
                "custom_subject": msg.custom_subject,
            }
        )

    # Get products for promotion message form
    from shop.models import Product

    products = Product.objects.filter(is_active=True).order_by("name")

    context = {
        "campaigns": campaigns,
        "timeline_campaigns": timeline_campaigns,
        "upcoming_messages": upcoming_messages_data,
        "recent_messages": recent_messages_data,
        "total_campaigns": total_campaigns,
        "active_campaigns": active_campaigns,
        "upcoming_campaigns": upcoming_campaigns,
        "total_messages": total_messages,
        "sent_messages": sent_messages,
        "products": products,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/campaigns_list.html", context)


@staff_member_required
def shipments_dashboard(request):
    """
    Shipments tracking dashboard for incoming inventory.
    """
    import json
    from datetime import date

    from django.http import JsonResponse

    from shop.models import Shipment

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create_shipment":
            import json as json_module
            import uuid
            from datetime import timedelta
            from decimal import Decimal

            from shop.models import ProductVariant, ShipmentItem

            try:
                tracking_number = request.POST.get("tracking_number", "").strip()
                supplier = request.POST.get("supplier", "").strip()
                expected_date = request.POST.get("expected_date")

                # Auto-generate tracking number if not provided
                if not tracking_number:
                    tracking_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"

                # Default expected date to 2 weeks if not provided
                if not expected_date:
                    expected_date = (timezone.now().date() + timedelta(days=14)).isoformat()

                shipment = Shipment.objects.create(
                    name=request.POST.get("name", "").strip(),
                    tracking_number=tracking_number,
                    supplier=supplier or "Unknown Supplier",
                    status=request.POST.get("status") or "pending",
                    date_shipped=request.POST.get("date_shipped") or None,
                    expected_date=expected_date,
                    date_received=request.POST.get("date_received") or None,
                    manufacturing_cost=request.POST.get("manufacturing_cost") or 0,
                    shipping_cost=request.POST.get("shipping_cost") or 0,
                    customs_duty=request.POST.get("customs_duty") or 0,
                    other_fees=request.POST.get("other_fees") or 0,
                    notes=request.POST.get("notes", ""),
                )

                # Create shipment items if provided
                new_items_json = request.POST.get("new_items", "[]")
                new_items = json_module.loads(new_items_json)

                for item_data in new_items:
                    variant_id = item_data.get("variant_id")
                    quantity = int(item_data.get("quantity", 0))
                    unit_cost = item_data.get("unit_cost")

                    if quantity <= 0:
                        continue

                    variant = ProductVariant.objects.select_related("product").get(id=variant_id)

                    # Use provided cost or auto-populate from variant/product
                    if unit_cost is not None and str(unit_cost).strip():
                        final_cost = Decimal(str(unit_cost))
                    elif variant.cost is not None:
                        final_cost = variant.cost
                    else:
                        final_cost = variant.product.base_cost or Decimal("0")

                    # If shipment is delivered, set received_quantity = quantity
                    received_qty = quantity if shipment.status == "delivered" else 0

                    ShipmentItem.objects.create(
                        shipment=shipment,
                        variant=variant,
                        quantity=quantity,
                        received_quantity=received_qty,
                        unit_cost=final_cost,
                    )

                    # If delivered, also update variant stock
                    if shipment.status == "delivered" and received_qty > 0:
                        variant.stock_quantity += received_qty
                        variant.save(update_fields=["stock_quantity"])

                return JsonResponse({
                    "success": True,
                    "shipment_id": shipment.id,
                    "tracking_number": shipment.tracking_number,
                })
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_shipment":
            try:
                from shop.models import ShipmentItem

                shipment_id = request.POST.get("shipment_id")
                shipment = Shipment.objects.get(id=shipment_id)

                # Track old status to detect delivery
                old_status = shipment.status
                new_status = request.POST.get("status")

                shipment.name = request.POST.get("name", "").strip()
                shipment.tracking_number = request.POST.get("tracking_number")
                shipment.supplier = request.POST.get("supplier")
                shipment.status = new_status
                shipment.date_shipped = request.POST.get("date_shipped") or None
                shipment.expected_date = request.POST.get("expected_date")
                shipment.date_received = request.POST.get("date_received") or None
                shipment.manufacturing_cost = request.POST.get("manufacturing_cost") or 0
                shipment.shipping_cost = request.POST.get("shipping_cost") or 0
                shipment.customs_duty = request.POST.get("customs_duty") or 0
                shipment.other_fees = request.POST.get("other_fees") or 0
                shipment.notes = request.POST.get("notes", "")

                # Set date received if status is delivered and not already set
                if shipment.status == "delivered" and not shipment.date_received:
                    shipment.date_received = date.today()

                shipment.save()

                # If status changed TO delivered, add received quantities to variant stock
                if old_status != "delivered" and new_status == "delivered":
                    for item in shipment.items.select_related("variant"):
                        # Use received_quantity if set, otherwise default to quantity
                        qty_to_add = item.received_quantity if item.received_quantity > 0 else item.quantity
                        if qty_to_add > 0:
                            # If received_quantity wasn't set, update it to match quantity
                            if item.received_quantity == 0:
                                item.received_quantity = item.quantity
                                item.save(update_fields=["received_quantity"])
                            item.variant.stock_quantity += qty_to_add
                            item.variant.save(update_fields=["stock_quantity"])

                # If status changed FROM delivered to something else, reverse the stock
                elif old_status == "delivered" and new_status != "delivered":
                    for item in shipment.items.select_related("variant"):
                        qty_to_remove = item.received_quantity if item.received_quantity > 0 else item.quantity
                        if qty_to_remove > 0:
                            item.variant.stock_quantity = max(0, item.variant.stock_quantity - qty_to_remove)
                            item.variant.save(update_fields=["stock_quantity"])

                # Update shipment items
                for key, value in request.POST.items():
                    if key.startswith("item_") and "_quantity" in key:
                        item_id = key.split("_")[1]
                        try:
                            item = ShipmentItem.objects.get(id=item_id, shipment=shipment)
                            if key.endswith("_quantity"):
                                item.quantity = value
                            elif key.endswith("_received_quantity"):
                                item.received_quantity = value
                        except ShipmentItem.DoesNotExist:
                            pass
                    elif key.startswith("item_") and "_unit_cost" in key:
                        item_id = key.split("_")[1]
                        try:
                            item = ShipmentItem.objects.get(id=item_id, shipment=shipment)
                            item.unit_cost = value
                            item.save()
                        except ShipmentItem.DoesNotExist:
                            pass

                # Save all items
                for item in shipment.items.all():
                    quantity_key = f"item_{item.id}_quantity"
                    received_key = f"item_{item.id}_received_quantity"
                    cost_key = f"item_{item.id}_unit_cost"

                    if quantity_key in request.POST:
                        item.quantity = request.POST.get(quantity_key)
                    if received_key in request.POST:
                        item.received_quantity = request.POST.get(received_key)
                    if cost_key in request.POST:
                        item.unit_cost = request.POST.get(cost_key)
                    item.save()

                return JsonResponse({"success": True})
            except Shipment.DoesNotExist:
                return JsonResponse({"success": False, "error": "Shipment not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_shipment_item":
            try:
                from shop.models import ShipmentItem

                item_id = request.POST.get("item_id")
                item = ShipmentItem.objects.get(id=item_id)

                item.quantity = request.POST.get("quantity")
                item.received_quantity = request.POST.get("received_quantity")
                item.unit_cost = request.POST.get("unit_cost")

                item.save()
                return JsonResponse({"success": True})
            except ShipmentItem.DoesNotExist:
                return JsonResponse({"success": False, "error": "Shipment item not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "add_shipment_item":
            try:
                from shop.models import ProductVariant, ShipmentItem

                shipment_id = request.POST.get("shipment_id")
                variant_id = request.POST.get("variant_id")
                quantity = request.POST.get("quantity", 0)
                unit_cost = request.POST.get("unit_cost", 0)

                shipment = Shipment.objects.get(id=shipment_id)
                variant = ProductVariant.objects.get(id=variant_id)

                # Check if this variant already exists in the shipment
                existing_item = ShipmentItem.objects.filter(
                    shipment=shipment, variant=variant
                ).first()

                if existing_item:
                    # Add to existing quantity instead of erroring
                    existing_item.quantity += int(quantity)
                    # Update cost if provided (use new cost for the additional quantity)
                    if unit_cost:
                        existing_item.unit_cost = unit_cost
                    existing_item.save()
                    item = existing_item
                    was_updated = True
                else:
                    item = ShipmentItem.objects.create(
                        shipment=shipment,
                        variant=variant,
                        quantity=quantity,
                        received_quantity=0,
                        unit_cost=unit_cost,
                    )
                    was_updated = False

                return JsonResponse(
                    {
                        "success": True,
                        "updated": was_updated,
                        "item": {
                            "id": item.id,
                            "variant_id": variant.id,
                            "variant_sku": variant.sku,
                            "variant_name": f"{variant.product.name} - {variant.size.label if variant.size else ''} {variant.color.name if variant.color else ''}",
                            "quantity": item.quantity,
                            "received_quantity": item.received_quantity,
                            "unit_cost": float(item.unit_cost),
                            "total_cost": float(item.total_cost),
                        },
                    }
                )
            except Shipment.DoesNotExist:
                return JsonResponse({"success": False, "error": "Shipment not found"})
            except ProductVariant.DoesNotExist:
                return JsonResponse({"success": False, "error": "Variant not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "bulk_add_shipment_items":
            # Add multiple variants at once from matrix UI
            try:
                import json as json_module

                from decimal import Decimal

                from shop.models import ProductVariant, ShipmentItem

                items_json = request.POST.get("items", "[]")
                items_to_add = json_module.loads(items_json)

                if not items_to_add:
                    return JsonResponse({"success": False, "error": "No items to add"})

                added_items = []
                for item_data in items_to_add:
                    variant_id = item_data.get("variant_id")
                    quantity = int(item_data.get("quantity", 0))
                    unit_cost = item_data.get("unit_cost")

                    if quantity <= 0:
                        continue

                    variant = ProductVariant.objects.select_related("product").get(id=variant_id)

                    # Auto-populate unit_cost from variant cost or product base_cost if not provided
                    if unit_cost is not None and str(unit_cost).strip():
                        final_cost = Decimal(str(unit_cost))
                    elif variant.cost is not None:
                        final_cost = variant.cost
                    else:
                        final_cost = variant.product.base_cost or Decimal("0")

                    size_label = variant.size.label if variant.size else ""
                    color_name = variant.color.name if variant.color else ""

                    added_items.append({
                        "id": None,
                        "variant_id": variant.id,
                        "variant_sku": variant.sku,
                        "variant_name": f"{variant.product.name} - {size_label} {color_name}".strip(),
                        "quantity": quantity,
                        "received_quantity": 0,
                        "unit_cost": float(final_cost),
                        "total_cost": float(quantity * final_cost),
                    })

                return JsonResponse({"success": True, "items": added_items})

            except ProductVariant.DoesNotExist:
                return JsonResponse({"success": False, "error": "Variant not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "delete_shipment_item":
            try:
                from shop.models import ShipmentItem

                item_id = request.POST.get("item_id")
                item = ShipmentItem.objects.get(id=item_id)
                item.delete()

                return JsonResponse({"success": True})
            except ShipmentItem.DoesNotExist:
                return JsonResponse({"success": False, "error": "Shipment item not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "delete_shipment":
            try:
                from shop.models import ShipmentItem

                shipment_id = request.POST.get("shipment_id")
                shipment = Shipment.objects.get(id=shipment_id)

                # If delivered, subtract stock from variants
                if shipment.status == "delivered":
                    items = ShipmentItem.objects.filter(shipment=shipment).select_related("variant")
                    for item in items:
                        variant = item.variant
                        # Subtract received quantity (use received_quantity if set, else quantity)
                        qty_to_subtract = item.received_quantity if item.received_quantity > 0 else item.quantity
                        variant.stock_quantity = max(0, variant.stock_quantity - qty_to_subtract)
                        variant.save(update_fields=["stock_quantity"])

                shipment.delete()
                return JsonResponse({"success": True})
            except Shipment.DoesNotExist:
                return JsonResponse({"success": False, "error": "Shipment not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

    # Get all shipments
    shipments = Shipment.objects.all()

    # Calculate stats
    stats = {
        "pending": shipments.filter(status="pending").count(),
        "in_transit": shipments.filter(status="in-transit").count(),
        "delivered": shipments.filter(status="delivered").count(),
        "delayed": shipments.filter(status="delayed").count(),
    }

    # Calculate metrics
    from django.db.models import Avg

    # Average shipping time (days from shipped to received)
    delivered_shipments = shipments.filter(
        status="delivered", date_shipped__isnull=False, date_received__isnull=False
    )
    avg_shipping_days = 0
    if delivered_shipments.exists():
        total_days = 0
        count = 0
        for ship in delivered_shipments:
            if ship.date_shipped and ship.date_received:
                days = (ship.date_received - ship.date_shipped).days
                total_days += days
                count += 1
        avg_shipping_days = round(total_days / count, 1) if count > 0 else 0

    # Average costs across all shipments
    metrics = {
        "avg_shipping_days": avg_shipping_days,
        "avg_manufacturing_cost": shipments.aggregate(avg=Avg("manufacturing_cost"))["avg"] or 0,
        "avg_shipping_cost": shipments.aggregate(avg=Avg("shipping_cost"))["avg"] or 0,
        "avg_customs_duty": shipments.aggregate(avg=Avg("customs_duty"))["avg"] or 0,
        "avg_other_fees": shipments.aggregate(avg=Avg("other_fees"))["avg"] or 0,
    }

    # Prepare data for template and JSON
    shipments_data = []
    for shipment in shipments:
        # Get items for this shipment
        items_data = []
        for item in shipment.items.all():
            # Calculate stock impact for deletion warning
            qty_received = item.received_quantity if item.received_quantity > 0 else item.quantity
            current_stock = item.variant.stock_quantity
            stock_after_delete = current_stock - qty_received if shipment.status == "delivered" else current_stock

            items_data.append(
                {
                    "id": item.id,
                    "variant_id": item.variant.id,
                    "variant_sku": item.variant.sku,
                    "variant_name": f"{item.variant.product.name} - {item.variant.size.label if item.variant.size else ''} {item.variant.color.name if item.variant.color else ''}",
                    "quantity": item.quantity,
                    "received_quantity": item.received_quantity,
                    "sold_quantity": item.sold_quantity,
                    "available_quantity": item.available_quantity,
                    "unit_cost": float(item.unit_cost),
                    "total_cost": float(item.total_cost),
                    "current_stock": current_stock,
                    "stock_after_delete": max(0, stock_after_delete),
                    "would_go_negative": stock_after_delete < 0,
                }
            )

        shipments_data.append(
            {
                "id": shipment.id,
                "name": shipment.name,
                "tracking_number": shipment.tracking_number,
                "supplier": shipment.supplier,
                "status": shipment.status,
                "date_shipped": (
                    shipment.date_shipped.isoformat() if shipment.date_shipped else None
                ),
                "expected_date": shipment.expected_date.isoformat(),
                "date_received": (
                    shipment.date_received.isoformat() if shipment.date_received else None
                ),
                "manufacturing_cost": float(shipment.manufacturing_cost),
                "shipping_cost": float(shipment.shipping_cost),
                "customs_duty": float(shipment.customs_duty),
                "other_fees": float(shipment.other_fees),
                "total_cost": float(shipment.total_cost),
                "item_count": shipment.item_count,
                "variant_count": shipment.variant_count,
                "items": items_data,
                "notes": shipment.notes,
            }
        )

    # Get all product variants for the variant selector
    from shop.models import Product, ProductVariant

    all_variants = ProductVariant.objects.select_related(
        "product", "size", "color"
    ).all()

    variants_data = []
    for variant in all_variants:
        size_label = variant.size.label if variant.size else ""
        color_name = variant.color.name if variant.color else ""
        variant_display = f"{variant.product.name} - {size_label} {color_name}".strip()

        variants_data.append(
            {
                "id": variant.id,
                "sku": variant.sku,
                "display_name": variant_display,
                "product_name": variant.product.name,
                "product_id": variant.product.id,
                "size": size_label,
                "color": color_name,
                "cost": float(variant.cost) if variant.cost else None,
            }
        )

    # Get products with variants grouped for matrix view
    products_for_matrix = []
    all_products = Product.objects.prefetch_related(
        "variants__size", "variants__color"
    ).filter(variants__isnull=False).distinct()

    for product in all_products:
        # Get all sizes and colors for this product
        sizes = set()
        colors = set()
        variants_map = {}

        for variant in product.variants.all():
            size_label = variant.size.label if variant.size else "One Size"
            color_name = variant.color.name if variant.color else "Default"
            sizes.add(size_label)
            colors.add(color_name)
            # Map (size, color) -> variant data
            key = f"{size_label}|{color_name}"
            variants_map[key] = {
                "id": variant.id,
                "sku": variant.sku,
                "cost": float(variant.cost) if variant.cost else float(product.base_cost or 0),
                "stock": variant.stock_quantity,
            }

        products_for_matrix.append({
            "id": product.id,
            "name": product.name,
            "base_cost": float(product.base_cost or 0),
            "sizes": sorted(list(sizes)),
            "colors": sorted(list(colors)),
            "variants": variants_map,
        })

    # Get unique suppliers for autocomplete
    saved_suppliers = list(
        Shipment.objects.exclude(supplier="")
        .exclude(supplier="Unknown Supplier")
        .values_list("supplier", flat=True)
        .distinct()
        .order_by("supplier")
    )

    context = {
        "shipments": shipments_data,
        "shipments_json": json.dumps(shipments_data, default=str),
        "variants": variants_data,
        "variants_json": json.dumps(variants_data, default=str),
        "products_for_matrix": products_for_matrix,
        "products_for_matrix_json": json.dumps(products_for_matrix, default=str),
        "saved_suppliers": saved_suppliers,
        "saved_suppliers_json": json.dumps(saved_suppliers),
        "stats": stats,
        "metrics": metrics,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/shipments_dashboard.html", context)


@staff_member_required
def orders_dashboard(request):
    """
    Orders management dashboard.
    """
    import json

    from django.db.models import Count, Sum
    from django.http import JsonResponse

    from shop.models import Order, OrderItem

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "update_order_status":
            try:
                order_id = request.POST.get("order_id")
                order = Order.objects.get(id=order_id)
                order.status = request.POST.get("status")
                order.save()
                return JsonResponse({"success": True})
            except Order.DoesNotExist:
                return JsonResponse({"success": False, "error": "Order not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "process_refund":
            try:
                import stripe
                from django.conf import settings
                from shop.models import OrderStatus

                order_id = request.POST.get("order_id")
                order = Order.objects.get(id=order_id)

                # Only paid orders can be refunded
                if order.status != OrderStatus.PAID:
                    return JsonResponse({"success": False, "error": "Only PAID orders can be refunded."})

                # Need a payment intent to refund
                if not order.stripe_payment_intent_id:
                    return JsonResponse({"success": False, "error": "No payment intent found for this order."})

                # Use production Stripe keys
                stripe.api_key = settings.STRIPE_SECRET_KEY

                # Create refund in Stripe
                refund = stripe.Refund.create(
                    payment_intent=order.stripe_payment_intent_id,
                )

                # Update order status
                order.status = OrderStatus.REFUNDED
                order.save()

                return JsonResponse({
                    "success": True,
                    "refund_id": refund.id,
                    "message": f"Refund processed successfully. Order #{order.id} is now REFUNDED.",
                })
            except Order.DoesNotExist:
                return JsonResponse({"success": False, "error": "Order not found"})
            except stripe.StripeError as e:
                return JsonResponse({"success": False, "error": str(e)})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "get_order_items":
            try:
                order_id = request.POST.get("order_id")
                order = Order.objects.get(id=order_id)

                items_data = []
                for item in order.items.select_related("variant", "shipment_item__shipment"):
                    shipment_info = None
                    if item.shipment_item:
                        shipment_info = {
                            "id": item.shipment_item.shipment.id,
                            "tracking": item.shipment_item.shipment.tracking_number,
                            "name": item.shipment_item.shipment.name,
                            "supplier": item.shipment_item.shipment.supplier,
                            "date_received": item.shipment_item.shipment.date_received.isoformat() if item.shipment_item.shipment.date_received else None,
                        }

                    items_data.append({
                        "id": item.id,
                        "sku": item.sku,
                        "variant_name": f"{item.variant.product.name} - {item.variant.size.label if item.variant and item.variant.size else ''} {item.variant.color.name if item.variant and item.variant.color else ''}" if item.variant else item.sku,
                        "quantity": item.quantity,
                        "line_total": float(item.line_total),
                        "unit_cost": float(item.unit_cost) if item.unit_cost else None,
                        "profit": float(item.profit) if item.profit is not None else None,
                        "profit_margin": round(item.profit_margin, 1) if item.profit_margin is not None else None,
                        "shipment": shipment_info,
                    })

                return JsonResponse({"success": True, "items": items_data})
            except Order.DoesNotExist:
                return JsonResponse({"success": False, "error": "Order not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

    # Check if we should show test orders (hidden by default)
    show_test_orders = request.GET.get("show_test", "false").lower() == "true"

    # Get orders (exclude test orders by default)
    orders = Order.objects.all().select_related("user").prefetch_related("items")
    if not show_test_orders:
        orders = orders.filter(is_test=False)

    # Calculate stats using OrderStatus choices (always exclude test orders from stats)
    from shop.models import OrderStatus

    real_orders = Order.objects.filter(is_test=False)
    stats = {
        "total": real_orders.count(),
        "pending": real_orders.filter(status=OrderStatus.CREATED).count(),
        "processing": real_orders.filter(status=OrderStatus.AWAITING_PAYMENT).count(),
        "shipped": real_orders.filter(status=OrderStatus.SHIPPED).count(),
        "delivered": real_orders.filter(status=OrderStatus.FULFILLED).count(),
        "total_revenue": real_orders.filter(status=OrderStatus.PAID).aggregate(Sum("total"))[
            "total__sum"
        ]
        or 0,
    }

    # Prepare orders data
    orders_data = []
    for order in orders[:50]:  # Limit to 50 most recent
        user_name = f"{order.user.first_name} {order.user.last_name}" if order.user else "Guest"

        # Calculate profit for this order
        total_cost = 0
        items_with_cost = 0
        for item in order.items.all():
            if item.unit_cost is not None:
                total_cost += float(item.unit_cost) * item.quantity
                items_with_cost += 1

        profit = float(order.subtotal) - total_cost if items_with_cost > 0 else None

        orders_data.append(
            {
                "id": order.id,
                "order_number": f"#{order.id}",
                "customer_name": user_name,
                "customer_email": order.email or (order.user.email if order.user else ""),
                "status": order.status,
                "subtotal": float(order.subtotal),
                "tax": float(order.tax),
                "shipping": float(order.shipping),
                "total": float(order.total),
                "cost": total_cost if items_with_cost > 0 else None,
                "profit": profit,
                "profit_margin": (profit / float(order.subtotal) * 100) if profit and order.subtotal > 0 else None,
                "stripe_payment_intent": order.stripe_payment_intent_id,
                "tracking_number": order.tracking_number,
                "carrier": order.carrier,
                "label_url": order.label_url,
                "created_at": order.created_at.isoformat(),
                "item_count": order.items.count(),
            }
        )

    # Count test orders for the toggle display
    test_orders_count = Order.objects.filter(is_test=True).count()

    context = {
        "orders": orders_data,
        "orders_json": json.dumps(orders_data),
        "stats": stats,
        "show_test_orders": show_test_orders,
        "test_orders_count": test_orders_count,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/orders_dashboard.html", context)


@staff_member_required
def search_variants_for_order(request):
    """
    AJAX endpoint to search products/variants for manual order creation.
    Returns variants with product info, SKU, attributes, price, and stock.
    """
    from django.http import JsonResponse
    from django.db.models import Q
    from shop.models import ProductVariant

    if request.method == "GET":
        query = request.GET.get("q", "").strip()
        if len(query) < 2:
            return JsonResponse({"results": []})

        # Search by product name or SKU
        variants = ProductVariant.objects.filter(
            Q(product__name__icontains=query) | Q(sku__icontains=query)
        ).filter(
            is_active=True,
            product__is_active=True
        ).select_related(
            "product", "size", "color"
        ).prefetch_related(
            "attributes__attribute"
        )[:20]

        results = []
        for variant in variants:
            # Build attribute display string
            attrs = []
            for av in variant.attributes.select_related('attribute').order_by('attribute__display_order'):
                attrs.append(f"{av.attribute.name}: {av.value}")
            # Fallback to legacy fields
            if not attrs:
                if variant.size:
                    attrs.append(f"Size: {variant.size.label or variant.size.code}")
                if variant.color:
                    attrs.append(f"Color: {variant.color.name}")

            results.append({
                "id": variant.id,
                "product_name": variant.product.name,
                "sku": variant.sku or f"V-{variant.id}",
                "attributes": ", ".join(attrs),
                "price": float(variant.price),
                "stock": variant.stock_quantity,
                "display_name": f"{variant.product.name} - {', '.join(attrs)}" if attrs else variant.product.name,
            })

        return JsonResponse({"results": results})

    return JsonResponse({"error": "Invalid method"}, status=405)


@staff_member_required
def add_manual_order(request):
    """
    Add a manual order with optional product line items.
    Supports both historical imports (totals only) and new manual orders (with products).
    """
    if request.method == "POST":
        try:
            import json
            from decimal import Decimal
            from datetime import datetime
            from django.http import JsonResponse
            from shop.models import Address, Order, OrderItem, OrderStatus, User, ProductVariant

            # Get form data
            customer_name = request.POST.get("customer_name", "").strip()
            customer_email = request.POST.get("customer_email", "").strip()
            customer_phone = request.POST.get("customer_phone", "").strip()
            order_date = request.POST.get("order_date")
            status = request.POST.get("status", "PAID")
            notes = request.POST.get("notes", "")

            # Get shipping address fields
            shipping_line1 = request.POST.get("shipping_line1", "").strip()
            shipping_line2 = request.POST.get("shipping_line2", "").strip()
            shipping_city = request.POST.get("shipping_city", "").strip()
            shipping_region = request.POST.get("shipping_region", "").strip()
            shipping_postal = request.POST.get("shipping_postal", "").strip()
            shipping_country = request.POST.get("shipping_country", "US").strip()

            # Check if using line items or manual totals
            use_line_items = request.POST.get("use_line_items") == "true"
            line_items_json = request.POST.get("line_items", "[]")
            decrement_stock = request.POST.get("decrement_stock") == "true"

            # Try to find the user by email
            try:
                user = User.objects.get(email=customer_email)
            except User.DoesNotExist:
                user = None

            # Parse the order date
            order_datetime = timezone.make_aware(
                datetime.strptime(order_date, "%Y-%m-%d")
            )

            # Get discount (applies to both modes)
            discount = Decimal(request.POST.get("discount", "0"))

            if use_line_items:
                # Parse line items and calculate totals
                line_items = json.loads(line_items_json)

                if not line_items:
                    return JsonResponse({"success": False, "error": "No line items provided"})

                # Calculate subtotal from line items
                subtotal = Decimal("0")
                for item in line_items:
                    subtotal += Decimal(str(item["price"])) * int(item["quantity"])

                tax = Decimal(request.POST.get("tax", "0"))
                shipping = Decimal(request.POST.get("shipping", "0"))
                total = subtotal - discount + tax + shipping
                # Ensure total doesn't go negative
                if total < 0:
                    total = Decimal("0")
            else:
                # Manual totals (historical import)
                subtotal = Decimal(request.POST.get("subtotal", "0"))
                tax = Decimal(request.POST.get("tax", "0"))
                shipping = Decimal(request.POST.get("shipping", "0"))
                total = Decimal(request.POST.get("total", "0"))
                line_items = []

            # Create shipping address if provided
            shipping_address = None
            if shipping_line1 and shipping_city and shipping_postal:
                shipping_address = Address.objects.create(
                    full_name=customer_name or "Customer",
                    line1=shipping_line1,
                    line2=shipping_line2,
                    city=shipping_city,
                    region=shipping_region,
                    postal_code=shipping_postal,
                    country=shipping_country,
                    email=customer_email,
                )

            # Create the order
            order = Order.objects.create(
                user=user,
                customer_name=customer_name,
                email=customer_email,
                phone=customer_phone,
                shipping_address=shipping_address,
                subtotal=subtotal,
                tax=tax,
                shipping=shipping,
                total=total,
                status=status,
                created_at=order_datetime,
                updated_at=timezone.now(),
                stripe_payment_intent_id=f"MANUAL_{order_datetime.strftime('%Y%m%d')}_{timezone.now().strftime('%H%M%S')}",
            )

            # Create OrderItems if line items provided
            for item in line_items:
                variant_id = item.get("variant_id")
                quantity = int(item["quantity"])
                price = Decimal(str(item["price"]))

                variant = None
                sku = item.get("sku", "MANUAL")
                unit_cost = None

                if variant_id:
                    try:
                        variant = ProductVariant.objects.get(id=variant_id)
                        sku = variant.sku or f"V-{variant.id}"
                        unit_cost = variant.cost

                        # Optionally decrement stock
                        if decrement_stock and variant.stock_quantity >= quantity:
                            variant.stock_quantity -= quantity
                            variant.save(update_fields=["stock_quantity"])
                    except ProductVariant.DoesNotExist:
                        pass

                order_item = OrderItem.objects.create(
                    order=order,
                    variant=variant,
                    sku=sku,
                    quantity=quantity,
                    line_total=price * quantity,
                    unit_cost=unit_cost,
                )

                # Try to allocate from shipments for cost tracking
                if variant:
                    order_item.allocate_from_shipments()

            return JsonResponse({
                "success": True,
                "order_id": order.id,
                "message": f"Manual order #{order.id} created successfully",
                "items_created": len(line_items),
            })

        except Exception as e:
            return JsonResponse({
                "success": False,
                "error": str(e)
            })

    return JsonResponse({"success": False, "error": "Invalid request method"})


@staff_member_required
def users_dashboard(request):
    """
    User accounts management dashboard with comprehensive information.
    """
    import json

    from django.contrib.auth.models import User
    from django.db.models import Count, Max, Q, Sum

    from shop.models import Cart, Order, PageView, SavedAddress, UserProfile, VisitorSession

    # Get all customer users (exclude staff and admin accounts)
    users = (
        User.objects.filter(is_staff=False, is_superuser=False)
        .select_related("profile")
        .prefetch_related("cart_set", "saved_addresses")
        .annotate(
            order_count=Count("order"),
            total_spent=Sum("order__total"),
            last_order_date=Max("order__created_at"),
            cart_items_count=Count("cart__items"),
        )
        .order_by("-date_joined")
    )

    # Calculate stats
    stats = {
        "total_users": users.count(),
        "users_with_orders": users.filter(order_count__gt=0).count(),
        "active_carts": Cart.objects.filter(items__isnull=False).distinct().count(),
        "total_page_views": PageView.objects.count(),
    }

    # Prepare users data
    users_data = []
    for user in users:
        # Get profile info
        try:
            profile = user.profile
            phone = profile.phone_number or ""
        except UserProfile.DoesNotExist:
            phone = ""

        # Get current cart info
        current_cart = None
        cart_total = 0
        try:
            cart = user.cart_set.filter(items__isnull=False).first()
            if cart:
                cart_total = cart.total
                current_cart = {"item_count": cart.items.count(), "total": float(cart_total)}
        except:
            pass

        # Get recent page views - VisitorSession is tracked by session_id, not user
        recent_views = []
        # Note: Can't directly link VisitorSession to User since they're session-based

        # Get saved addresses
        addresses = []
        try:
            for addr in user.saved_addresses.all()[:3]:
                addresses.append(
                    {
                        "label": addr.label,
                        "address": f"{addr.street_address}, {addr.city}, {addr.state} {addr.zip_code}",
                    }
                )
        except:
            pass

        users_data.append(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "full_name": f"{user.first_name} {user.last_name}".strip() or user.username,
                "phone": phone,
                "date_joined": user.date_joined.isoformat(),
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "is_active": user.is_active,
                "order_count": user.order_count or 0,
                "total_spent": float(user.total_spent) if user.total_spent else 0,
                "last_order_date": (
                    user.last_order_date.isoformat() if user.last_order_date else None
                ),
                "current_cart": current_cart,
                "page_views_count": 0,  # Can't link VisitorSession to User directly
                "last_visit": None,  # Can't link VisitorSession to User directly
                "recent_views": recent_views,
                "saved_addresses": addresses,
            }
        )

    context = {
        "users": users_data,
        "users_json": json.dumps(users_data, default=str),
        "stats": stats,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/users_dashboard.html", context)


@staff_member_required
def returns_dashboard(request):
    """
    Customer returns management dashboard.
    Supports creating returns, updating status, adding tracking, and processing refunds.
    """
    import json
    from decimal import Decimal

    from django.http import JsonResponse

    from shop.models import (
        Order,
        OrderItem,
        OrderStatus,
        Return,
        ReturnItem,
        ReturnReason,
        ReturnStatus,
    )

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create_return":
            try:
                order_id = request.POST.get("order_id")
                reason = request.POST.get("reason")
                customer_notes = request.POST.get("customer_notes", "")
                item_ids = request.POST.getlist("item_ids")
                quantities = request.POST.getlist("quantities")

                order = Order.objects.get(id=order_id)

                # Create the return
                return_request = Return.objects.create(
                    order=order,
                    reason=reason,
                    customer_notes=customer_notes,
                    status=ReturnStatus.REQUESTED,
                )

                # Create return items
                for item_id, qty in zip(item_ids, quantities):
                    qty = int(qty)
                    if qty > 0:
                        order_item = OrderItem.objects.get(id=item_id)
                        # Calculate refund amount per item
                        unit_price = order_item.line_total / order_item.quantity
                        refund_amount = unit_price * qty
                        ReturnItem.objects.create(
                            return_request=return_request,
                            order_item=order_item,
                            quantity=qty,
                            refund_amount=refund_amount,
                        )

                return JsonResponse({
                    "success": True,
                    "return_id": return_request.id,
                    "message": f"Return #{return_request.id} created successfully.",
                })
            except Order.DoesNotExist:
                return JsonResponse({"success": False, "error": "Order not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_status":
            try:
                return_id = request.POST.get("return_id")
                new_status = request.POST.get("status")

                return_request = Return.objects.get(id=return_id)
                old_status = return_request.status
                return_request.status = new_status

                # Set timestamps based on status transitions
                if new_status == ReturnStatus.APPROVED and old_status != ReturnStatus.APPROVED:
                    return_request.approved_at = timezone.now()
                elif new_status == ReturnStatus.RECEIVED and old_status != ReturnStatus.RECEIVED:
                    return_request.received_at = timezone.now()
                    # Mark all items as received
                    return_request.items.update(received=True)
                elif new_status == ReturnStatus.REFUNDED and old_status != ReturnStatus.REFUNDED:
                    return_request.refunded_at = timezone.now()

                return_request.save()

                return JsonResponse({
                    "success": True,
                    "message": f"Return #{return_id} status updated to {new_status}.",
                })
            except Return.DoesNotExist:
                return JsonResponse({"success": False, "error": "Return not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "add_tracking":
            try:
                return_id = request.POST.get("return_id")
                tracking_number = request.POST.get("tracking_number")
                carrier = request.POST.get("carrier")

                return_request = Return.objects.get(id=return_id)
                return_request.tracking_number = tracking_number
                return_request.carrier = carrier

                # Optionally update status to IN_TRANSIT
                if return_request.status in [ReturnStatus.APPROVED, ReturnStatus.AWAITING_SHIPMENT]:
                    return_request.status = ReturnStatus.IN_TRANSIT

                return_request.save()

                return JsonResponse({
                    "success": True,
                    "message": f"Tracking info added to Return #{return_id}.",
                })
            except Return.DoesNotExist:
                return JsonResponse({"success": False, "error": "Return not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "generate_label":
            try:
                import easypost
                from django.conf import settings

                return_id = request.POST.get("return_id")
                return_request = Return.objects.get(id=return_id)
                order = return_request.order

                if not order.shipping_address:
                    return JsonResponse({"success": False, "error": "Order has no shipping address"})

                # Initialize EasyPost
                client = easypost.EasyPostClient(settings.EASYPOST_API_KEY)

                # Create return shipment (swap from/to addresses)
                # Customer is sending back to us
                from_address = client.address.create(
                    name=order.shipping_address.full_name,
                    street1=order.shipping_address.line1,
                    street2=order.shipping_address.line2 or "",
                    city=order.shipping_address.city,
                    state=order.shipping_address.region,
                    zip=order.shipping_address.postal_code,
                    country=order.shipping_address.country,
                )

                # Our return address (from site settings or default)
                to_address = client.address.create(
                    company="Blueprint Apparel",
                    street1="123 Main St",
                    city="Austin",
                    state="TX",
                    zip="78701",
                    country="US",
                )

                # Create parcel (default small package)
                parcel = client.parcel.create(
                    length=10,
                    width=8,
                    height=4,
                    weight=16,
                )

                # Create shipment
                shipment = client.shipment.create(
                    from_address=from_address,
                    to_address=to_address,
                    parcel=parcel,
                    is_return=True,
                )

                # Buy cheapest rate
                lowest_rate = shipment.lowest_rate()
                bought_shipment = client.shipment.buy(shipment.id, rate=lowest_rate)

                # Update return with tracking info
                return_request.tracking_number = bought_shipment.tracking_code
                return_request.carrier = lowest_rate.carrier
                return_request.return_label_url = bought_shipment.postage_label.label_url
                return_request.status = ReturnStatus.AWAITING_SHIPMENT
                return_request.save()

                return JsonResponse({
                    "success": True,
                    "tracking_number": bought_shipment.tracking_code,
                    "carrier": lowest_rate.carrier,
                    "label_url": bought_shipment.postage_label.label_url,
                    "cost": str(lowest_rate.rate),
                    "message": f"Return label generated. Cost: ${lowest_rate.rate}",
                })
            except Return.DoesNotExist:
                return JsonResponse({"success": False, "error": "Return not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "mark_item_received":
            try:
                return_item_id = request.POST.get("return_item_id")
                condition_notes = request.POST.get("condition_notes", "")

                return_item = ReturnItem.objects.get(id=return_item_id)
                return_item.received = True
                return_item.condition_notes = condition_notes
                return_item.save()

                # Check if all items received
                return_request = return_item.return_request
                if return_request.all_items_received:
                    return_request.status = ReturnStatus.RECEIVED
                    return_request.received_at = timezone.now()
                    return_request.save()

                return JsonResponse({
                    "success": True,
                    "all_received": return_request.all_items_received,
                    "message": f"Item marked as received.",
                })
            except ReturnItem.DoesNotExist:
                return JsonResponse({"success": False, "error": "Return item not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "process_refund":
            try:
                import stripe
                from django.conf import settings

                return_id = request.POST.get("return_id")
                custom_amount = request.POST.get("refund_amount")

                return_request = Return.objects.get(id=return_id)
                order = return_request.order

                if not order.stripe_payment_intent_id:
                    return JsonResponse({"success": False, "error": "No payment intent found for this order."})

                # Calculate refund amount
                if custom_amount:
                    refund_amount = Decimal(custom_amount)
                else:
                    refund_amount = return_request.total_refund_amount

                # Convert to cents for Stripe
                refund_amount_cents = int(refund_amount * 100)

                # Initialize Stripe
                stripe.api_key = settings.STRIPE_SECRET_KEY

                # Create refund
                refund = stripe.Refund.create(
                    payment_intent=order.stripe_payment_intent_id,
                    amount=refund_amount_cents,
                )

                # Update return
                return_request.refund_amount = refund_amount
                return_request.stripe_refund_id = refund.id
                return_request.status = ReturnStatus.REFUNDED
                return_request.refunded_at = timezone.now()
                return_request.save()

                return JsonResponse({
                    "success": True,
                    "refund_id": refund.id,
                    "amount": str(refund_amount),
                    "message": f"Refund of ${refund_amount} processed successfully.",
                })
            except Return.DoesNotExist:
                return JsonResponse({"success": False, "error": "Return not found"})
            except stripe.StripeError as e:
                return JsonResponse({"success": False, "error": str(e)})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "add_notes":
            try:
                return_id = request.POST.get("return_id")
                admin_notes = request.POST.get("admin_notes")

                return_request = Return.objects.get(id=return_id)
                return_request.admin_notes = admin_notes
                return_request.save()

                return JsonResponse({
                    "success": True,
                    "message": "Notes saved.",
                })
            except Return.DoesNotExist:
                return JsonResponse({"success": False, "error": "Return not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "get_order_items":
            try:
                order_id = request.POST.get("order_id")
                order = Order.objects.get(id=order_id)

                items_data = []
                for item in order.items.select_related("variant", "variant__product"):
                    product_name = ""
                    if item.variant and item.variant.product:
                        product_name = item.variant.product.name
                    items_data.append({
                        "id": item.id,
                        "sku": item.sku,
                        "product_name": product_name,
                        "quantity": item.quantity,
                        "line_total": str(item.line_total),
                        "unit_price": str(item.line_total / item.quantity) if item.quantity > 0 else "0",
                    })

                return JsonResponse({
                    "success": True,
                    "items": items_data,
                })
            except Order.DoesNotExist:
                return JsonResponse({"success": False, "error": "Order not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

    # GET request - display dashboard
    returns = Return.objects.select_related("order").prefetch_related(
        "items__order_item__variant__product"
    ).all()

    # Get orders for create return dropdown (paid, shipped, or fulfilled orders)
    eligible_orders = Order.objects.filter(
        status__in=[OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.FULFILLED]
    ).order_by("-created_at")[:100]

    # Build return data for template
    returns_data = []
    for r in returns:
        items_list = []
        for item in r.items.all():
            product_name = ""
            if item.order_item.variant and item.order_item.variant.product:
                product_name = item.order_item.variant.product.name
            items_list.append({
                "id": item.id,
                "sku": item.order_item.sku,
                "product_name": product_name,
                "quantity": item.quantity,
                "refund_amount": str(item.refund_amount),
                "received": item.received,
                "condition_notes": item.condition_notes,
            })

        returns_data.append({
            "id": r.id,
            "order_id": r.order_id,
            "order_number": f"#{r.order_id}",
            "status": r.status,
            "reason": r.reason,
            "reason_display": r.get_reason_display(),
            "customer_notes": r.customer_notes,
            "admin_notes": r.admin_notes,
            "tracking_number": r.tracking_number,
            "carrier": r.carrier,
            "return_label_url": r.return_label_url,
            "refund_amount": str(r.refund_amount) if r.refund_amount else None,
            "total_refund_amount": str(r.total_refund_amount),
            "stripe_refund_id": r.stripe_refund_id,
            "created_at": r.created_at.isoformat(),
            "approved_at": r.approved_at.isoformat() if r.approved_at else None,
            "received_at": r.received_at.isoformat() if r.received_at else None,
            "refunded_at": r.refunded_at.isoformat() if r.refunded_at else None,
            "items": items_list,
            "all_items_received": r.all_items_received,
            "customer_email": r.order.email,
        })

    # Calculate stats
    stats = {
        "total": returns.count(),
        "requested": returns.filter(status=ReturnStatus.REQUESTED).count(),
        "approved": returns.filter(status=ReturnStatus.APPROVED).count(),
        "awaiting_shipment": returns.filter(status=ReturnStatus.AWAITING_SHIPMENT).count(),
        "in_transit": returns.filter(status=ReturnStatus.IN_TRANSIT).count(),
        "received": returns.filter(status=ReturnStatus.RECEIVED).count(),
        "refunded": returns.filter(status=ReturnStatus.REFUNDED).count(),
    }

    # Prepare orders for dropdown
    orders_data = []
    for order in eligible_orders:
        orders_data.append({
            "id": order.id,
            "order_number": f"#{order.id}",
            "email": order.email,
            "total": str(order.total),
            "status": order.status,
            "created_at": order.created_at.strftime("%b %d, %Y"),
        })

    context = {
        "returns": returns_data,
        "returns_json": json.dumps(returns_data),
        "orders": orders_data,
        "orders_json": json.dumps(orders_data),
        "stats": stats,
        "return_statuses": ReturnStatus.choices,
        "return_reasons": ReturnReason.choices,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/returns_dashboard.html", context)


@staff_member_required
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
                "order_number": f"#{order.id}",
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


@staff_member_required
def generate_shipping_label(request, order_id):
    """
    Auto-generate shipping label using cheapest rate from EasyPost.
    """
    from django.http import JsonResponse

    from shop.models import Order
    from shop.utils.shipping_helper import create_shipping_label, get_shipping_rates

    try:
        order = Order.objects.get(id=order_id)

        # Get all available rates
        rates = get_shipping_rates(order)

        if not rates:
            return JsonResponse(
                {"success": False, "error": "No shipping rates available. Check EasyPost configuration."},
                status=400,
            )

        # Use cheapest rate
        cheapest_rate = rates[0]

        # Create label
        result = create_shipping_label(order, cheapest_rate["id"], cheapest_rate["provider"])

        return JsonResponse(
            {
                "success": True,
                "tracking_number": result["tracking_number"],
                "carrier": result["carrier"],
                "label_url": result["label_url"],
                "cost": result["cost"],
            }
        )

    except Order.DoesNotExist:
        return JsonResponse({"success": False, "error": "Order not found"}, status=404)
    except Exception as e:
        logger.error(f"Error generating shipping label: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@staff_member_required
def manual_tracking(request, order_id):
    """
    Manually enter tracking information (for Pirate Ship, etc.).
    """
    from django.http import JsonResponse

    from shop.models import Order
    from shop.utils.shipping_helper import manual_tracking_entry

    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST required"}, status=405)

    try:
        order = Order.objects.get(id=order_id)

        tracking_number = request.POST.get("tracking_number", "").strip()
        carrier = request.POST.get("carrier", "").strip()

        if not tracking_number or not carrier:
            return JsonResponse(
                {"success": False, "error": "Tracking number and carrier are required"}, status=400
            )

        result = manual_tracking_entry(order, tracking_number, carrier)

        return JsonResponse(
            {
                "success": True,
                "tracking_number": result["tracking_number"],
                "carrier": result["carrier"],
            }
        )

    except Order.DoesNotExist:
        return JsonResponse({"success": False, "error": "Order not found"}, status=404)
    except Exception as e:
        logger.error(f"Error saving manual tracking: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
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


@staff_member_required
def bundles_dashboard(request):
    """
    Dashboard for managing product bundles.
    """
    from django.utils.text import slugify
    from .models import Bundle, BundleItem, Product

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "upload_bundle_image":
            # Upload and optimize bundle image
            from django.core.files.base import ContentFile
            from shop.utils.image_optimizer import optimize_image
            import io

            try:
                image_data = request.POST.get("image_data")
                if not image_data:
                    return JsonResponse({"success": False, "error": "No image data provided"})

                if "base64," not in image_data:
                    return JsonResponse({"success": False, "error": "Invalid image format"})

                format_part, data_part = image_data.split("base64,", 1)
                image_content = base64.b64decode(data_part)

                if len(image_content) == 0:
                    return JsonResponse({"success": False, "error": "Empty image"})

                # Optimize image
                original_size = len(image_content)
                optimized_content, filename, content_type = optimize_image(
                    io.BytesIO(image_content),
                    filename=f"bundle_{uuid.uuid4().hex[:8]}"
                )
                optimized_size = len(optimized_content)

                # Save to media folder
                from django.core.files.storage import default_storage
                path = default_storage.save(f"bundles/{filename}", ContentFile(optimized_content))
                url = default_storage.url(path)

                savings = round((1 - optimized_size / original_size) * 100, 1) if original_size > 0 else 0
                logger.info(f"Bundle image optimized: {original_size} -> {optimized_size} bytes ({savings}% reduction)")

                return JsonResponse({"success": True, "url": url})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "create":
            import json
            name = request.POST.get("name")
            price = request.POST.get("price")
            use_component_pricing = request.POST.get("use_component_pricing") == "on"
            description = request.POST.get("description", "")
            product_ids = request.POST.getlist("product_ids")
            images_json = request.POST.get("images", "[]")
            try:
                images = json.loads(images_json) if images_json else []
            except json.JSONDecodeError:
                images = []

            if not name or (not use_component_pricing and not price):
                messages.error(request, "Name and price are required (unless using component pricing)")
                return redirect("admin_bundles")

            try:
                # Generate unique slug
                base_slug = slugify(name)
                slug = base_slug
                counter = 1
                while Bundle.objects.filter(slug=slug).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1

                bundle = Bundle.objects.create(
                    name=name,
                    slug=slug,
                    price=price if not use_component_pricing else None,
                    use_component_pricing=use_component_pricing,
                    description=description,
                    images=images,
                    show_includes=request.POST.get("show_includes") == "on",
                    is_active=True,
                    available_for_purchase=True,
                )

                # Add products to bundle
                for i, product_id in enumerate(product_ids):
                    if product_id:
                        product = Product.objects.get(id=product_id)
                        BundleItem.objects.create(
                            bundle=bundle,
                            product=product,
                            quantity=1,
                            display_order=i,
                        )

                messages.success(request, f'Bundle "{bundle.name}" created successfully!')
            except Exception as e:
                messages.error(request, f"Error creating bundle: {str(e)}")

            return redirect("admin_bundles")

        elif action == "update":
            import json
            bundle_id = request.POST.get("bundle_id")
            try:
                bundle = Bundle.objects.get(id=bundle_id)
                bundle.name = request.POST.get("name")
                use_component_pricing = request.POST.get("use_component_pricing") == "on"
                bundle.use_component_pricing = use_component_pricing
                bundle.price = request.POST.get("price") if not use_component_pricing else None
                bundle.description = request.POST.get("description", "")
                bundle.show_includes = request.POST.get("show_includes") == "on"
                bundle.is_active = request.POST.get("is_active") == "on"
                bundle.available_for_purchase = request.POST.get("available_for_purchase") == "on"
                bundle.featured = request.POST.get("featured") == "on"
                # Handle images
                images_json = request.POST.get("images", "[]")
                try:
                    bundle.images = json.loads(images_json) if images_json else []
                except json.JSONDecodeError:
                    pass  # Keep existing images if JSON is invalid
                bundle.save()

                # Update products
                product_ids = request.POST.getlist("product_ids")
                bundle.items.all().delete()
                for i, product_id in enumerate(product_ids):
                    if product_id:
                        product = Product.objects.get(id=product_id)
                        BundleItem.objects.create(
                            bundle=bundle,
                            product=product,
                            quantity=1,
                            display_order=i,
                        )

                messages.success(request, f'Bundle "{bundle.name}" updated!')
            except Bundle.DoesNotExist:
                messages.error(request, "Bundle not found")
            except Exception as e:
                messages.error(request, f"Error: {str(e)}")

            return redirect("admin_bundles")

        elif action == "delete":
            bundle_id = request.POST.get("bundle_id")
            try:
                bundle = Bundle.objects.get(id=bundle_id)
                name = bundle.name
                bundle.delete()
                messages.success(request, f'Bundle "{name}" deleted!')
            except Bundle.DoesNotExist:
                messages.error(request, "Bundle not found")

            return redirect("admin_bundles")

        elif action == "toggle_active":
            bundle_id = request.POST.get("bundle_id")
            try:
                bundle = Bundle.objects.get(id=bundle_id)
                bundle.is_active = not bundle.is_active
                bundle.save()
                status = "activated" if bundle.is_active else "deactivated"
                messages.success(request, f'Bundle "{bundle.name}" {status}!')
            except Bundle.DoesNotExist:
                messages.error(request, "Bundle not found")

            return redirect("admin_bundles")

    # Get all bundles
    bundles = Bundle.objects.prefetch_related("items__product").all().order_by("-created_at")

    # Build availability data for each bundle
    bundles_with_stock = []
    for bundle in bundles:
        available_sizes = bundle.get_available_sizes()
        size_stock_data = []
        total_available = 0

        for size in available_sizes:
            variants_for_size = bundle.get_variants_for_size(size)
            skus = []
            max_qty = 999

            if variants_for_size:
                for item, variant in variants_for_size:
                    skus.append(variant.sku)
                    available_bundles = variant.stock_quantity // item.quantity
                    max_qty = min(max_qty, available_bundles)

            if max_qty != 999 and max_qty > 0:
                size_stock_data.append({
                    "size": size.label or size.code,
                    "quantity": max_qty,
                    "skus": skus,
                })
                total_available += max_qty

        bundles_with_stock.append({
            "bundle": bundle,
            "size_stock": size_stock_data,
            "total_available": total_available,
        })

    # Get all products for the create/edit form
    products = Product.objects.filter(is_active=True).order_by("name")

    context = {
        "bundles_with_stock": bundles_with_stock,
        "products": products,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/bundles_dashboard.html", context)


@staff_member_required
@two_factor_required
def test_center(request):
    """
    Test Center for testing Stripe purchases, discounts, and refunds.
    Uses Stripe test keys to create real test transactions.
    """
    from decimal import Decimal

    import stripe
    from django.conf import settings

    from shop.models import Discount, Order, OrderStatus, Product

    # Check if test keys are configured
    test_secret_key = settings.STRIPE_TEST_SECRET_KEY
    test_publishable_key = settings.STRIPE_TEST_PUBLISHABLE_KEY
    test_keys_configured = bool(test_secret_key and test_publishable_key)

    # If test keys not configured, render page with message instead of redirecting
    if not test_keys_configured:
        context = {
            "test_orders": [],
            "test_orders_json": "[]",
            "products": [],
            "test_products": [],
            "discounts": [],
            "stripe_publishable_key": "",
            "test_keys_configured": False,
            "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
        }
        return render(request, "admin/test_center.html", context)

    # Use test keys for all Stripe operations in this view
    stripe.api_key = test_secret_key

    # Get test orders
    test_orders = Order.objects.filter(is_test=True).order_by("-created_at")[:20]

    # Get products for the dropdown
    products = Product.objects.filter(is_active=True).order_by("name")

    # Get active discount codes
    discounts = Discount.objects.filter(is_active=True).order_by("name")

    # Handle POST actions
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create_test_order":
            try:
                amount = Decimal(request.POST.get("amount", "10.00"))
                product_id = request.POST.get("product_id")
                description = request.POST.get("description", "Test order")
                auto_pay = request.POST.get("auto_pay") == "true"
                payment_method = request.POST.get("payment_method", "pm_card_visa")

                # Create Stripe PaymentIntent
                intent_params = {
                    "amount": int(amount * 100),  # Convert to cents
                    "currency": "usd",
                    "description": f"Test Center: {description}",
                    "metadata": {
                        "test_center": "true",
                        "product_id": product_id or "",
                    },
                    "payment_method_types": ["card"],  # Only accept cards, no redirects
                }

                # If auto_pay, use a test payment method and confirm immediately
                if auto_pay:
                    intent_params["payment_method"] = payment_method
                    intent_params["confirm"] = True

                intent = stripe.PaymentIntent.create(**intent_params)

                # Determine order status based on payment
                if auto_pay and intent.status == "succeeded":
                    order_status = OrderStatus.PAID
                else:
                    order_status = OrderStatus.AWAITING_PAYMENT

                # Create test order
                order = Order.objects.create(
                    email="test@testcenter.local",
                    status=order_status,
                    subtotal=amount,
                    shipping=Decimal("0.00"),
                    tax=Decimal("0.00"),
                    total=amount,
                    stripe_payment_intent_id=intent.id,
                    is_test=True,
                )

                if auto_pay and intent.status == "succeeded":
                    return JsonResponse({
                        "success": True,
                        "auto_paid": True,
                        "order_id": order.id,
                        "payment_intent_id": intent.id,
                        "message": f"Test order #{order.id} created and paid!",
                    })
                else:
                    return JsonResponse({
                        "success": True,
                        "auto_paid": False,
                        "order_id": order.id,
                        "payment_intent_id": intent.id,
                        "client_secret": intent.client_secret,
                        "message": f"Test order #{order.id} created. Use Stripe test card to complete payment.",
                    })

            except stripe.StripeError as e:
                # For card errors, extract the user-friendly message
                error_msg = str(e)
                if hasattr(e, 'user_message'):
                    error_msg = e.user_message
                return JsonResponse({"success": False, "error": error_msg, "declined": True})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "confirm_test_payment":
            try:
                payment_intent_id = request.POST.get("payment_intent_id")
                order_id = request.POST.get("order_id")

                # Retrieve the PaymentIntent to check status
                intent = stripe.PaymentIntent.retrieve(payment_intent_id)

                order = Order.objects.get(id=order_id, is_test=True)

                if intent.status == "succeeded":
                    order.status = OrderStatus.PAID
                    order.save()
                    return JsonResponse({
                        "success": True,
                        "message": f"Payment confirmed! Order #{order.id} is now PAID.",
                    })
                else:
                    return JsonResponse({
                        "success": False,
                        "error": f"Payment not yet succeeded. Status: {intent.status}",
                    })

            except Order.DoesNotExist:
                return JsonResponse({"success": False, "error": "Test order not found"})
            except stripe.StripeError as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "apply_discount":
            try:
                discount_code = request.POST.get("discount_code", "").strip().upper()
                cart_total = Decimal(request.POST.get("cart_total", "100.00"))

                # Find the discount
                try:
                    discount = Discount.objects.get(code__iexact=discount_code, is_active=True)
                except Discount.DoesNotExist:
                    return JsonResponse({"success": False, "error": f"Discount code '{discount_code}' not found or inactive."})

                # Check validity
                now = timezone.now()
                if discount.valid_from > now:
                    return JsonResponse({"success": False, "error": "Discount code is not yet active."})
                if discount.valid_until and discount.valid_until < now:
                    return JsonResponse({"success": False, "error": "Discount code has expired."})
                if discount.min_purchase_amount and cart_total < discount.min_purchase_amount:
                    return JsonResponse({
                        "success": False,
                        "error": f"Minimum purchase of ${discount.min_purchase_amount} required."
                    })
                if discount.max_uses and discount.times_used >= discount.max_uses:
                    return JsonResponse({"success": False, "error": "Discount code has reached its usage limit."})

                # Calculate discount
                if discount.discount_type == "percentage":
                    discount_amount = cart_total * (discount.value / 100)
                    discount_display = f"{discount.value}% off"
                elif discount.discount_type == "fixed":
                    discount_amount = min(discount.value, cart_total)
                    discount_display = f"${discount.value} off"
                elif discount.discount_type == "free_shipping":
                    discount_amount = Decimal("0.00")  # Would affect shipping
                    discount_display = "Free shipping"
                else:
                    discount_amount = Decimal("0.00")
                    discount_display = discount.discount_type

                final_total = cart_total - discount_amount

                return JsonResponse({
                    "success": True,
                    "discount_name": discount.name,
                    "discount_type": discount.discount_type,
                    "discount_display": discount_display,
                    "discount_amount": float(discount_amount),
                    "original_total": float(cart_total),
                    "final_total": float(final_total),
                    "times_used": discount.times_used,
                    "max_uses": discount.max_uses,
                })

            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "process_refund":
            try:
                order_id = request.POST.get("order_id")
                order = Order.objects.get(id=order_id, is_test=True)

                if not order.stripe_payment_intent_id:
                    return JsonResponse({"success": False, "error": "No Stripe payment intent found for this order."})

                if order.status != OrderStatus.PAID:
                    return JsonResponse({"success": False, "error": "Only PAID orders can be refunded."})

                # Create refund in Stripe
                refund = stripe.Refund.create(
                    payment_intent=order.stripe_payment_intent_id,
                )

                # Update order status
                order.status = OrderStatus.REFUNDED
                order.save()

                return JsonResponse({
                    "success": True,
                    "refund_id": refund.id,
                    "message": f"Refund processed successfully. Order #{order.id} is now REFUNDED.",
                })

            except Order.DoesNotExist:
                return JsonResponse({"success": False, "error": "Test order not found"})
            except stripe.StripeError as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "delete_test_order":
            try:
                order_id = request.POST.get("order_id")
                order = Order.objects.get(id=order_id, is_test=True)
                order.delete()
                return JsonResponse({
                    "success": True,
                    "message": f"Test order #{order_id} deleted.",
                })
            except Order.DoesNotExist:
                return JsonResponse({"success": False, "error": "Test order not found"})

        elif action == "create_test_product":
            try:
                import uuid
                from shop.models import Color, OrderItem, Product, ProductVariant, Size

                name = request.POST.get("name", "Test Item")
                price = Decimal(request.POST.get("price", "1.00"))
                create_order = request.POST.get("create_order") == "true"

                # Generate unique slug
                unique_id = str(uuid.uuid4())[:8]
                slug = f"test-product-{unique_id}"

                # Get or create Size M
                size_m, _ = Size.objects.get_or_create(
                    code="M",
                    defaults={"label": "Medium"}
                )

                # Get or create Color Black
                color_black, _ = Color.objects.get_or_create(
                    name="Black"
                )

                # Placeholder image (gray box with package icon)
                placeholder_svg = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='400' viewBox='0 0 400 400'%3E%3Crect fill='%23e2e8f0' width='400' height='400'/%3E%3Cpath d='M200 120l60 35v70l-60 35-60-35v-70l60-35z' fill='none' stroke='%2394a3b8' stroke-width='8'/%3E%3Cpath d='M200 155v70M140 155l60 35 60-35' fill='none' stroke='%2394a3b8' stroke-width='8'/%3E%3C/svg%3E"

                # Create the product
                product = Product.objects.create(
                    name=name,
                    slug=slug,
                    description="",
                    base_price=price,
                    is_active=True,
                    available_for_purchase=True,
                    images=[placeholder_svg],
                )

                # Create variant with stock
                variant = ProductVariant.objects.create(
                    product=product,
                    size=size_m,
                    color=color_black,
                    stock_quantity=100,
                    price=price,
                )
                variant.refresh_from_db()  # Get auto-generated SKU

                response_data = {
                    "success": True,
                    "message": f"Test product '{name}' created!",
                    "product_id": product.id,
                    "product_name": product.name,
                    "variant_id": variant.id,
                    "variant_sku": variant.sku,
                }

                # Optionally create a paid test order
                if create_order:
                    # Create Stripe PaymentIntent and auto-pay
                    intent = stripe.PaymentIntent.create(
                        amount=int(price * 100),
                        currency="usd",
                        description=f"Test Center: {name}",
                        metadata={"test_center": "true", "product_id": str(product.id)},
                        payment_method_types=["card"],
                        payment_method="pm_card_visa",
                        confirm=True,
                    )

                    # Create test order
                    order = Order.objects.create(
                        email="test@testcenter.local",
                        status=OrderStatus.PAID,
                        subtotal=price,
                        shipping=Decimal("0.00"),
                        tax=Decimal("0.00"),
                        total=price,
                        stripe_payment_intent_id=intent.id,
                        is_test=True,
                    )

                    # Create order item
                    OrderItem.objects.create(
                        order=order,
                        variant=variant,
                        sku=variant.sku,
                        quantity=1,
                        line_total=price,
                    )

                    response_data["order_id"] = order.id
                    response_data["message"] = f"Test product '{name}' and paid order #{order.id} created!"

                return JsonResponse(response_data)

            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "delete_test_product":
            try:
                from shop.models import CartItem, Product

                product_id = request.POST.get("product_id")
                product = Product.objects.get(id=product_id)

                # Check it's a test product (slug starts with test-product-)
                if not product.slug.startswith("test-product-"):
                    return JsonResponse({"success": False, "error": "Can only delete test products"})

                # Delete cart items referencing this product's variants
                variant_ids = product.variants.values_list("id", flat=True)
                deleted_cart_items = CartItem.objects.filter(variant_id__in=variant_ids).delete()[0]

                # Now delete the product (cascades to variants)
                product_name = product.name
                product.delete()

                msg = f"Deleted '{product_name}'"
                if deleted_cart_items:
                    msg += f" and {deleted_cart_items} cart item(s)"

                return JsonResponse({"success": True, "message": msg})

            except Product.DoesNotExist:
                return JsonResponse({"success": False, "error": "Product not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

    # Prepare test orders data
    test_orders_data = []
    for order in test_orders:
        test_orders_data.append({
            "id": order.id,
            "total": float(order.total),
            "status": order.status,
            "stripe_payment_intent_id": order.stripe_payment_intent_id,
            "created_at": order.created_at.isoformat(),
        })

    # Get test products (slug starts with test-product-)
    test_products = Product.objects.filter(slug__startswith="test-product-").order_by("-id")[:20]

    context = {
        "test_orders": test_orders_data,
        "test_orders_json": json.dumps(test_orders_data),
        "products": products,
        "test_products": test_products,
        "discounts": discounts,
        "stripe_publishable_key": test_publishable_key,
        "test_keys_configured": bool(test_secret_key and test_publishable_key),
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/test_center.html", context)


@staff_member_required
def test_checkout(request):
    """
    Quick test checkout - creates a $1 test product, adds to cart, redirects to checkout.
    Staff only.
    """
    from decimal import Decimal
    from django.shortcuts import redirect

    from shop.cart_utils import add_to_cart, get_or_create_cart
    from shop.models import Color, Product, ProductVariant, Size

    # Find or create the reusable test product
    test_product = Product.objects.filter(slug="test-checkout-item").first()

    # Ensure existing test product is hidden from inventory
    if test_product and test_product.is_active:
        test_product.is_active = False
        test_product.save(update_fields=["is_active"])

    if not test_product:
        # Create Size M and Color Black if needed
        size_m, _ = Size.objects.get_or_create(code="M", defaults={"label": "Medium"})
        color_black, _ = Color.objects.get_or_create(name="Black")

        # Placeholder image
        placeholder_svg = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='400' viewBox='0 0 400 400'%3E%3Crect fill='%23e2e8f0' width='400' height='400'/%3E%3Cpath d='M200 120l60 35v70l-60 35-60-35v-70l60-35z' fill='none' stroke='%2394a3b8' stroke-width='8'/%3E%3Cpath d='M200 155v70M140 155l60 35 60-35' fill='none' stroke='%2394a3b8' stroke-width='8'/%3E%3C/svg%3E"

        test_product = Product.objects.create(
            name="Test Checkout Item",
            slug="test-checkout-item",
            description="System test product - excluded from inventory",
            base_price=Decimal("1.00"),
            is_active=False,  # Hidden from shop and inventory reports
            available_for_purchase=True,
            images=[placeholder_svg],
        )

        ProductVariant.objects.create(
            product=test_product,
            size=size_m,
            color=color_black,
            stock_quantity=100,  # Minimal stock for testing
            price=Decimal("1.00"),
            images=[placeholder_svg],
        )

    # Get the variant and ensure it has placeholder image
    variant = test_product.variants.first()
    placeholder_svg = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='400' viewBox='0 0 400 400'%3E%3Crect fill='%23e2e8f0' width='400' height='400'/%3E%3Cpath d='M200 120l60 35v70l-60 35-60-35v-70l60-35z' fill='none' stroke='%2394a3b8' stroke-width='8'/%3E%3Cpath d='M200 155v70M140 155l60 35 60-35' fill='none' stroke='%2394a3b8' stroke-width='8'/%3E%3C/svg%3E"
    if not variant.images:
        variant.images = [placeholder_svg]
        variant.save()

    # Clear cart and add test item
    cart = get_or_create_cart(request)
    cart.items.all().delete()
    cart.bundle_items.all().delete()
    add_to_cart(request, variant.id, quantity=1)

    # Redirect to checkout
    return redirect("shop:checkout")
