import csv
import io
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import get_user_model
from .models import EmailSubscription

User = get_user_model()


@staff_member_required
def subscribers_list(request):
    """
    Display list of email subscribers and registered users.
    Only accessible to admin/staff users.
    Handles CSV upload for bulk subscriber and user import.
    """
    # Handle Delete Actions
    if request.method == 'POST' and request.POST.get('delete_action'):
        delete_action = request.POST.get('delete_action')
        delete_id = request.POST.get('delete_id')

        try:
            if delete_action == 'subscriber':
                subscriber = EmailSubscription.objects.get(id=delete_id)
                email = subscriber.email
                subscriber.delete()
                messages.success(request, f'Successfully deleted subscriber: {email}')
            elif delete_action == 'user':
                user = User.objects.get(id=delete_id)
                # Prevent deleting staff users
                if user.is_staff:
                    messages.error(request, 'Cannot delete staff users')
                else:
                    username = user.username
                    user.delete()
                    messages.success(request, f'Successfully deleted user: {username}')
        except EmailSubscription.DoesNotExist:
            messages.error(request, 'Subscriber not found')
        except User.DoesNotExist:
            messages.error(request, 'User not found')
        except Exception as e:
            messages.error(request, f'Error deleting: {str(e)}')

        return redirect('admin_subscribers')

    # Handle Single Subscriber Addition
    if request.method == 'POST' and request.POST.get('single_email'):
        email = request.POST.get('single_email', '').strip().lower()

        if email:
            try:
                subscriber, created = EmailSubscription.objects.get_or_create(
                    email=email,
                    defaults={
                        'source': 'admin_manual',
                        'is_confirmed': False
                    }
                )
                if created:
                    messages.success(request, f'Successfully added {email}')
                else:
                    messages.info(request, f'{email} is already subscribed')
            except Exception as e:
                messages.error(request, f'Error adding subscriber: {str(e)}')
        else:
            messages.error(request, 'Please provide a valid email address')

        return redirect('admin_subscribers')

    # Handle Subscriber CSV Upload
    if request.method == 'POST' and request.FILES.get('subscriber_csv'):
        csv_file = request.FILES['subscriber_csv']

        # Validate file extension
        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'Please upload a CSV file.')
            return redirect('admin_subscribers')

        try:
            # Read CSV file
            decoded_file = csv_file.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            csv_reader = csv.DictReader(io_string)

            added_count = 0
            skipped_count = 0
            errors = []

            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 (row 1 is header)
                email = row.get('email', '').strip().lower()
                is_confirmed = row.get('is_confirmed', '').strip().lower() in ['true', '1', 'yes']
                source = row.get('source', 'csv_upload').strip() or 'csv_upload'

                if not email:
                    errors.append(f"Row {row_num}: Missing email")
                    continue

                # Create or get subscriber
                try:
                    sub, created = EmailSubscription.objects.get_or_create(
                        email=email,
                        defaults={
                            'source': source,
                            'is_confirmed': is_confirmed
                        }
                    )
                    if created:
                        added_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    errors.append(f"Row {row_num} ({email}): {str(e)}")

            # Display results
            if added_count > 0:
                messages.success(request, f'Successfully added {added_count} new subscriber(s).')
            if skipped_count > 0:
                messages.info(request, f'Skipped {skipped_count} existing subscriber(s).')
            if errors:
                for error in errors[:5]:  # Show first 5 errors
                    messages.warning(request, error)
                if len(errors) > 5:
                    messages.warning(request, f'...and {len(errors) - 5} more errors.')

            return redirect('admin_subscribers')

        except Exception as e:
            messages.error(request, f'Error processing CSV: {str(e)}')
            return redirect('admin_subscribers')

    # Handle User CSV Upload
    if request.method == 'POST' and request.FILES.get('user_csv'):
        csv_file = request.FILES['user_csv']

        # Validate file extension
        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'Please upload a CSV file.')
            return redirect('admin_subscribers')

        try:
            # Read CSV file
            decoded_file = csv_file.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            csv_reader = csv.DictReader(io_string)

            added_count = 0
            skipped_count = 0
            errors = []

            for row_num, row in enumerate(csv_reader, start=2):
                username = row.get('username', '').strip()
                email = row.get('email', '').strip().lower()
                password = row.get('password', '').strip() or User.objects.make_random_password()

                if not username or not email:
                    errors.append(f"Row {row_num}: Missing username or email")
                    continue

                # Create user if doesn't exist
                try:
                    user, created = User.objects.get_or_create(
                        username=username,
                        defaults={
                            'email': email,
                        }
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
                messages.success(request, f'Successfully added {added_count} new user(s).')
            if skipped_count > 0:
                messages.info(request, f'Skipped {skipped_count} existing user(s).')
            if errors:
                for error in errors[:5]:  # Show first 5 errors
                    messages.warning(request, error)
                if len(errors) > 5:
                    messages.warning(request, f'...and {len(errors) - 5} more errors.')

            return redirect('admin_subscribers')

        except Exception as e:
            messages.error(request, f'Error processing CSV: {str(e)}')
            return redirect('admin_subscribers')

    # GET request - display page with pagination
    from django.core.paginator import Paginator

    # Pagination for subscribers
    subscribers_list = EmailSubscription.objects.all().order_by('-subscribed_at')
    subscribers_paginator = Paginator(subscribers_list, 10)  # 10 per page
    subscribers_page_number = request.GET.get('subscribers_page', 1)
    subscribers = subscribers_paginator.get_page(subscribers_page_number)

    # Pagination for users
    users_list = User.objects.all().order_by('-date_joined')
    users_paginator = Paginator(users_list, 10)  # 10 per page
    users_page_number = request.GET.get('users_page', 1)
    users = users_paginator.get_page(users_page_number)

    # Prepare subscriber growth data for chart
    from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
    from django.db.models import Count
    from datetime import datetime, timedelta

    # Get selected time period (default to 30 days)
    period = request.GET.get('period', '30')

    if period == '7':
        days_ago = 7
        date_format = '%b %d'
        trunc_func = TruncDate
        step_size = 1
    elif period == '90':
        days_ago = 90
        date_format = '%b %d'
        trunc_func = TruncDate
        step_size = 1
    elif period == 'weekly':
        days_ago = 84  # 12 weeks
        date_format = '%b %d'  # Format like "Oct 05"
        trunc_func = TruncWeek
        step_size = 7
    elif period == 'monthly':
        days_ago = 365  # 12 months
        date_format = '%b %Y'  # Format like "Nov 2023"
        trunc_func = TruncMonth
        step_size = 30
    else:  # default 30 days
        days_ago = 30
        date_format = '%b %d'
        trunc_func = TruncDate
        step_size = 1

    start_date = datetime.now() - timedelta(days=days_ago)
    end_date = datetime.now()

    # Get subscriber counts (no date filter - we'll handle the range in our date_dict)
    period_subscribers = (
        EmailSubscription.objects
        .annotate(date=trunc_func('subscribed_at'))
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )

    # Create data structure based on aggregation type
    if period == 'weekly':
        # Create complete week range with zero counts
        from datetime import date as dt_date
        date_dict = {}
        current_start = start_date.date()
        # Adjust to start of week (Sunday)
        # weekday() returns 0 for Monday, 6 for Sunday
        # To get Sunday, we calculate: (weekday + 1) % 7
        days_since_sunday = (current_start.weekday() + 1) % 7
        current_start = current_start - timedelta(days=days_since_sunday)

        # Get the Sunday of current week to ensure we include it
        today = datetime.now().date()
        days_since_sunday = (today.weekday() + 1) % 7
        end_week = today - timedelta(days=days_since_sunday)

        current = current_start
        while current <= end_week:
            date_dict[current] = 0
            current += timedelta(weeks=1)

        # Fill in actual counts - check all subscriber data
        for entry in period_subscribers:
            week_start = entry['date']
            # Convert datetime to date if needed
            if isinstance(week_start, datetime):
                week_start = week_start.date()
            # Only include weeks within our display range
            if week_start >= current_start and week_start <= end_week:
                if week_start not in date_dict:
                    date_dict[week_start] = 0
                date_dict[week_start] += entry['count']

        # Convert to chart data
        chart_labels = [date.strftime(date_format) for date in sorted(date_dict.keys())]
        chart_data = [date_dict[date] for date in sorted(date_dict.keys())]

    elif period == 'monthly':
        # Create complete month range with zero counts
        from dateutil.relativedelta import relativedelta
        date_dict = {}
        current_start = start_date.date().replace(day=1)  # Start of month
        end_month = datetime.now().date().replace(day=1)

        current = current_start
        while current <= end_month:
            date_dict[current] = 0
            current += relativedelta(months=1)

        # Fill in actual counts - check all subscriber data
        for entry in period_subscribers:
            month_start = entry['date']
            # Convert datetime to date if needed
            if isinstance(month_start, datetime):
                month_start = month_start.date()
            # Only include months within our display range
            if month_start >= current_start and month_start <= end_month:
                if month_start not in date_dict:
                    date_dict[month_start] = 0
                date_dict[month_start] += entry['count']

        # Convert to chart data
        chart_labels = [date.strftime(date_format) for date in sorted(date_dict.keys())]
        chart_data = [date_dict[date] for date in sorted(date_dict.keys())]

    else:
        # For daily, create complete date range with zero counts for missing days
        date_dict = {start_date.date() + timedelta(days=i): 0 for i in range(days_ago + 1)}
        for entry in period_subscribers:
            date_dict[entry['date']] = entry['count']

        # Convert to chart data
        chart_labels = [date.strftime(date_format) for date in sorted(date_dict.keys())]
        chart_data = [date_dict[date] for date in sorted(date_dict.keys())]

    # Calculate last 7 days signups
    from datetime import datetime, timedelta
    today = datetime.now()
    seven_days_ago = today - timedelta(days=7)
    fourteen_days_ago = today - timedelta(days=14)

    last_7_days_signups_list = subscribers_list.filter(subscribed_at__gte=seven_days_ago).order_by('-subscribed_at')
    last_7_days_signups = last_7_days_signups_list.count()

    # Calculate previous 7 days for comparison
    previous_7_days_signups = subscribers_list.filter(
        subscribed_at__gte=fourteen_days_ago,
        subscribed_at__lt=seven_days_ago
    ).count()

    # Calculate percentage change
    if previous_7_days_signups > 0:
        percent_change = ((last_7_days_signups - previous_7_days_signups) / previous_7_days_signups) * 100
    else:
        percent_change = 100 if last_7_days_signups > 0 else 0

    context = {
        'subscribers': subscribers,
        'users': users,
        'total_subscribers': subscribers_list.count(),
        'total_users': users_list.count(),
        'confirmed_subscribers': subscribers_list.filter(is_confirmed=True).count(),
        'last_7_days_signups': last_7_days_signups,
        'last_7_days_signups_list': last_7_days_signups_list,
        'last_7_days_percent_change': percent_change,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
        'selected_period': period,
        'server_time': datetime.now(),
    }

    return render(request, 'admin/subscribers_list.html', context)
