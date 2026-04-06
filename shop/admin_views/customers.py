"""
Customer, subscriber, and user management admin views.
"""

import csv
import io
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

import pytz

from shop.models import (
    EmailSubscription,
    SMSSubscription,
    UserProfile,
)

User = get_user_model()

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
                "date_joined": user.date_joined,
                "last_login": user.last_login,
                "is_active": user.is_active,
                "order_count": user.order_count or 0,
                "total_spent": float(user.total_spent) if user.total_spent else 0,
                "last_order_date": user.last_order_date,
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


