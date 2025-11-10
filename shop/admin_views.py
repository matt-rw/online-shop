import csv
import io
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from .models import EmailSubscription, ConnectionLog

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


@staff_member_required
def security_dashboard(request):
    """
    Display security and system stats dashboard.
    Only accessible to admin/staff users.
    """
    from datetime import datetime
    import sys
    import platform
    import django
    import os
    import psutil
    from django.conf import settings

    now = timezone.now()

    # System Information
    system_info = {
        'python_version': sys.version.split()[0],
        'django_version': django.get_version(),
        'platform': platform.platform(),
        'platform_system': platform.system(),
        'platform_release': platform.release(),
        'processor': platform.processor(),
        'architecture': platform.machine(),
        'hostname': platform.node(),
        'server_time': now,
    }

    # Machine Status (CPU, Memory, Disk)
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        machine_status = {
            'cpu_percent': round(cpu_percent, 1),
            'cpu_count': psutil.cpu_count(),
            'memory_total_gb': round(memory.total / (1024**3), 2),
            'memory_used_gb': round(memory.used / (1024**3), 2),
            'memory_percent': round(memory.percent, 1),
            'disk_total_gb': round(disk.total / (1024**3), 2),
            'disk_used_gb': round(disk.used / (1024**3), 2),
            'disk_percent': round(disk.percent, 1),
        }
    except:
        machine_status = {
            'cpu_percent': 'N/A',
            'cpu_count': 'N/A',
            'memory_total_gb': 'N/A',
            'memory_used_gb': 'N/A',
            'memory_percent': 'N/A',
            'disk_total_gb': 'N/A',
            'disk_used_gb': 'N/A',
            'disk_percent': 'N/A',
        }

    # Database Information
    try:
        from django.db import connection
        db_info = {
            'engine': settings.DATABASES['default']['ENGINE'].split('.')[-1],
            'name': settings.DATABASES['default']['NAME'],
            'host': settings.DATABASES['default'].get('HOST', 'localhost'),
            'port': settings.DATABASES['default'].get('PORT', 'default'),
        }

        # Get database size if PostgreSQL
        if 'postgresql' in settings.DATABASES['default']['ENGINE']:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_database_size(current_database());")
                db_size_bytes = cursor.fetchone()[0]
                db_size_mb = round(db_size_bytes / (1024 * 1024), 2)
                db_info['size'] = f"{db_size_mb} MB"
        else:
            db_info['size'] = 'N/A'
    except Exception as e:
        db_info = {
            'engine': 'Unknown',
            'name': 'Unknown',
            'host': 'Unknown',
            'port': 'Unknown',
            'size': 'N/A',
            'error': str(e)
        }

    # Django Settings Security Check
    django_settings = {
        'debug_mode': settings.DEBUG,
        'allowed_hosts': settings.ALLOWED_HOSTS,
        'secret_key_set': bool(settings.SECRET_KEY and len(settings.SECRET_KEY) > 20),
        'session_cookie_secure': getattr(settings, 'SESSION_COOKIE_SECURE', False),
        'csrf_cookie_secure': getattr(settings, 'CSRF_COOKIE_SECURE', False),
        'secure_ssl_redirect': getattr(settings, 'SECURE_SSL_REDIRECT', False),
        'secure_hsts_seconds': getattr(settings, 'SECURE_HSTS_SECONDS', 0),
        'static_root': bool(getattr(settings, 'STATIC_ROOT', None)),
        'media_root': bool(getattr(settings, 'MEDIA_ROOT', None)),
    }

    # HTTPS/TLS Status
    https_status = {
        'ssl_redirect': django_settings['secure_ssl_redirect'],
        'session_cookie_secure': django_settings['session_cookie_secure'],
        'csrf_cookie_secure': django_settings['csrf_cookie_secure'],
        'hsts_enabled': django_settings['secure_hsts_seconds'] > 0,
        'hsts_seconds': django_settings['secure_hsts_seconds'],
    }

    # Services Status (check if common services are running)
    services_status = []

    # Check if running under systemd/gunicorn
    try:
        running_processes = [p.name() for p in psutil.process_iter(['name'])]
        services_status.append({
            'name': 'Gunicorn',
            'status': 'running' if any('gunicorn' in p.lower() for p in running_processes) else 'not detected',
        })
        services_status.append({
            'name': 'Nginx',
            'status': 'running' if any('nginx' in p.lower() for p in running_processes) else 'not detected',
        })
        services_status.append({
            'name': 'PostgreSQL',
            'status': 'running' if any('postgres' in p.lower() for p in running_processes) else 'not detected',
        })
    except:
        services_status.append({
            'name': 'Process Check',
            'status': 'unavailable',
        })

    # Security Warnings
    warnings = []

    if django_settings['debug_mode']:
        warnings.append({
            'level': 'danger',
            'message': 'DEBUG mode is enabled! This should be disabled in production.'
        })

    if not django_settings['secret_key_set']:
        warnings.append({
            'level': 'danger',
            'message': 'SECRET_KEY is not properly configured.'
        })

    if not https_status['ssl_redirect']:
        warnings.append({
            'level': 'warning',
            'message': 'SECURE_SSL_REDIRECT is not enabled. HTTPS is not enforced.'
        })

    if not https_status['session_cookie_secure']:
        warnings.append({
            'level': 'warning',
            'message': 'SESSION_COOKIE_SECURE is False. Session cookies can be sent over HTTP.'
        })

    if not https_status['hsts_enabled']:
        warnings.append({
            'level': 'warning',
            'message': 'HSTS (HTTP Strict Transport Security) is not enabled.'
        })

    if settings.ALLOWED_HOSTS == ['*']:
        warnings.append({
            'level': 'danger',
            'message': 'ALLOWED_HOSTS is set to [\'*\']. This is insecure in production.'
        })

    # System resource warnings
    if machine_status['cpu_percent'] != 'N/A' and machine_status['cpu_percent'] > 80:
        warnings.append({
            'level': 'warning',
            'message': f'High CPU usage: {machine_status["cpu_percent"]}%'
        })

    if machine_status['memory_percent'] != 'N/A' and machine_status['memory_percent'] > 85:
        warnings.append({
            'level': 'warning',
            'message': f'High memory usage: {machine_status["memory_percent"]}%'
        })

    if machine_status['disk_percent'] != 'N/A' and machine_status['disk_percent'] > 90:
        warnings.append({
            'level': 'danger',
            'message': f'Critical disk usage: {machine_status["disk_percent"]}%'
        })

    # Get process info
    try:
        process_count = len(list(psutil.process_iter()))
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime_seconds = (now - timezone.make_aware(boot_time)).total_seconds()
        uptime_days = int(uptime_seconds // 86400)
        uptime_hours = int((uptime_seconds % 86400) // 3600)
        uptime_minutes = int((uptime_seconds % 3600) // 60)

        system_info['uptime'] = f"{uptime_days}d {uptime_hours}h {uptime_minutes}m"
        system_info['boot_time'] = boot_time
        system_info['process_count'] = process_count
    except:
        system_info['uptime'] = 'N/A'
        system_info['boot_time'] = 'N/A'
        system_info['process_count'] = 'N/A'

    # Network info
    try:
        import socket
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        system_info['local_ip'] = local_ip
    except:
        system_info['local_ip'] = 'N/A'

    # Additional metrics for user activity
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    staff_users = User.objects.filter(is_staff=True).count()

    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    recent_users_24h = User.objects.filter(date_joined__gte=last_24h).count()
    recent_users_7d = User.objects.filter(date_joined__gte=last_7d).count()

    user_metrics = {
        'total': total_users,
        'active': active_users,
        'staff': staff_users,
        'recent_24h': recent_users_24h,
        'recent_7d': recent_users_7d,
    }

    # Get recent connections from database
    recent_connections = ConnectionLog.objects.select_related('user').all()[:50]

    # Get unique IPs in last 24 hours
    unique_ips_24h = ConnectionLog.objects.filter(
        timestamp__gte=last_24h
    ).values('ip_address').distinct().count()

    # Get recent user logins (last login data)
    recent_logins = User.objects.exclude(last_login__isnull=True).order_by('-last_login')[:20]

    # Try to get request logs (if available)
    recent_logs = []
    try:
        import glob
        import os
        log_files = []

        # Common Django log locations
        possible_log_paths = [
            '/var/log/django/*.log',
            '/var/log/gunicorn/*.log',
            '/var/log/nginx/access.log',
            'logs/*.log',
            '*.log',
        ]

        for pattern in possible_log_paths:
            log_files.extend(glob.glob(pattern))

        if log_files:
            # Read last 50 lines from the most recent log file
            latest_log = max(log_files, key=os.path.getmtime)
            with open(latest_log, 'r') as f:
                lines = f.readlines()
                recent_logs = lines[-50:]  # Last 50 lines
        else:
            recent_logs = ['No log files found in standard locations']
    except Exception as e:
        recent_logs = [f'Unable to read logs: {str(e)}']

    # Email subscription metrics
    total_subs = EmailSubscription.objects.count()
    confirmed_subs = EmailSubscription.objects.filter(is_confirmed=True).count()
    recent_subs_24h = EmailSubscription.objects.filter(subscribed_at__gte=last_24h).count()

    email_metrics = {
        'total': total_subs,
        'confirmed': confirmed_subs,
        'recent_24h': recent_subs_24h,
        'confirmation_rate': round((confirmed_subs / total_subs * 100), 1) if total_subs > 0 else 0,
    }

    context = {
        'system_info': system_info,
        'machine_status': machine_status,
        'db_info': db_info,
        'django_settings': django_settings,
        'https_status': https_status,
        'services_status': services_status,
        'warnings': warnings,
        'user_metrics': user_metrics,
        'email_metrics': email_metrics,
        'recent_logins': recent_logins,
        'recent_logs': recent_logs,
        'recent_connections': recent_connections,
        'unique_ips_24h': unique_ips_24h,
    }

    return render(request, 'admin/security_dashboard.html', context)
