import csv
import io
import pytz
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta, datetime
from .models import (
    EmailSubscription, EmailTemplate, EmailCampaign, EmailLog,
    ConnectionLog, SMSSubscription, SMSTemplate, SMSCampaign, SMSLog,
    SiteSettings, Product, Campaign, CampaignMessage
)
from .decorators import two_factor_required

User = get_user_model()


@staff_member_required
@two_factor_required
def admin_home(request):
    """
    Central admin dashboard with quick access to all admin tools.
    Only accessible to admin/staff users.
    """
    from django.db.models import Sum
    from .models.analytics import PageView

    now = timezone.now()
    last_24h = now - timedelta(hours=24)

    # Quick stats
    stats = {
        'total_users': User.objects.count(),
        'total_email_subs': EmailSubscription.objects.count(),
        'total_sms_subs': SMSSubscription.objects.count(),
        'total_products': Product.objects.count(),
        'total_page_views': PageView.objects.count(),
        'page_views_24h': PageView.objects.filter(viewed_at__gte=last_24h).count(),
        'new_email_subs_24h': EmailSubscription.objects.filter(subscribed_at__gte=last_24h).count(),
        'new_sms_subs_24h': SMSSubscription.objects.filter(subscribed_at__gte=last_24h).count(),
        'email_campaigns': EmailCampaign.objects.count(),
        'sms_campaigns': SMSCampaign.objects.count(),
    }

    context = {
        'stats': stats,
        'cst_time': timezone.now().astimezone(pytz.timezone('America/Chicago')),
    }

    return render(request, 'admin/admin_home.html', context)


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

    # Handle CSV export
    if request.GET.get('export'):
        import csv
        from django.http import HttpResponse
        from shop.models import SMSSubscription

        export_type = request.GET.get('export')
        response = HttpResponse(content_type='text/csv')

        if export_type == 'email':
            response['Content-Disposition'] = 'attachment; filename="email_subscribers.csv"'
            writer = csv.writer(response)
            writer.writerow(['Email', 'Confirmed', 'Active', 'Source', 'Subscribed At'])

            for sub in EmailSubscription.objects.all().order_by('-subscribed_at'):
                writer.writerow([
                    sub.email,
                    'Yes' if sub.is_confirmed else 'No',
                    'Yes' if sub.is_active else 'No',
                    sub.source,
                    sub.subscribed_at.strftime('%Y-%m-%d %H:%M:%S')
                ])
        elif export_type == 'sms':
            response['Content-Disposition'] = 'attachment; filename="sms_subscribers.csv"'
            writer = csv.writer(response)
            writer.writerow(['Phone Number', 'Confirmed', 'Active', 'Source', 'Subscribed At'])

            for sub in SMSSubscription.objects.all().order_by('-subscribed_at'):
                writer.writerow([
                    sub.phone_number,
                    'Yes' if sub.is_confirmed else 'No',
                    'Yes' if sub.is_active else 'No',
                    sub.source,
                    sub.subscribed_at.strftime('%Y-%m-%d %H:%M:%S')
                ])
        else:  # all
            response['Content-Disposition'] = 'attachment; filename="all_subscribers.csv"'
            writer = csv.writer(response)
            writer.writerow(['Type', 'Contact', 'Confirmed', 'Active', 'Source', 'Subscribed At'])

            # Combine both lists
            all_subs = []
            for sub in EmailSubscription.objects.all():
                all_subs.append(('Email', sub.email, sub.is_confirmed, sub.is_active, sub.source, sub.subscribed_at))
            for sub in SMSSubscription.objects.all():
                all_subs.append(('SMS', sub.phone_number, sub.is_confirmed, sub.is_active, sub.source, sub.subscribed_at))

            # Sort by subscribed_at descending
            all_subs.sort(key=lambda x: x[5], reverse=True)

            for sub in all_subs:
                writer.writerow([
                    sub[0],
                    sub[1],
                    'Yes' if sub[2] else 'No',
                    'Yes' if sub[3] else 'No',
                    sub[4],
                    sub[5].strftime('%Y-%m-%d %H:%M:%S')
                ])

        return response

    # GET request - display all subscribers (both email and SMS)
    from shop.models import SMSSubscription
    import json
    from itertools import chain
    from operator import attrgetter

    # Get all email subscribers
    email_subscribers = EmailSubscription.objects.all().order_by('-subscribed_at')

    # Get all SMS subscribers
    sms_subscribers = SMSSubscription.objects.all().order_by('-subscribed_at')

    # Get unique count (people who may have both email and SMS)
    # For now, just count total unique records
    total_unique = email_subscribers.count() + sms_subscribers.count()

    # Get new subscribers in last 24 hours
    last_24h = timezone.now() - timedelta(hours=24)
    new_24h = (
        email_subscribers.filter(subscribed_at__gte=last_24h).count() +
        sms_subscribers.filter(subscribed_at__gte=last_24h).count()
    )

    # Generate chart data for different timeframes
    def generate_chart_data(days):
        from django.db.models.functions import TruncDate
        from django.db.models import Count
        from datetime import datetime, timedelta

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Get email subscriber counts by date
        email_data = (
            EmailSubscription.objects
            .filter(subscribed_at__gte=start_date)
            .annotate(date=TruncDate('subscribed_at'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )

        # Get SMS subscriber counts by date
        sms_data = (
            SMSSubscription.objects
            .filter(subscribed_at__gte=start_date)
            .annotate(date=TruncDate('subscribed_at'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
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
            date_dict_email[entry['date']] = entry['count']

        for entry in sms_data:
            date_dict_sms[entry['date']] = entry['count']

        # Generate labels and data arrays
        labels = []
        email_counts = []
        sms_counts = []

        for date in sorted(date_dict_email.keys()):
            if days <= 7:
                labels.append(date.strftime('%b %d'))
            elif days <= 90:
                labels.append(date.strftime('%m/%d'))
            else:
                labels.append(date.strftime('%b %d'))

            email_counts.append(date_dict_email[date])
            sms_counts.append(date_dict_sms[date])

        return {
            'labels': labels,
            'email': email_counts,
            'sms': sms_counts
        }

    # Generate chart data for all timeframes
    chart_data_7 = generate_chart_data(7)
    chart_data_30 = generate_chart_data(30)
    chart_data_90 = generate_chart_data(90)
    chart_data_365 = generate_chart_data(365)

    # Generate subscriber status breakdown data
    from django.db.models import Count, Q

    # Count different status categories across both email and SMS
    active_confirmed = (
        EmailSubscription.objects.filter(is_active=True, is_confirmed=True).count() +
        SMSSubscription.objects.filter(is_active=True, is_confirmed=True).count()
    )

    active_unconfirmed = (
        EmailSubscription.objects.filter(is_active=True, is_confirmed=False).count() +
        SMSSubscription.objects.filter(is_active=True, is_confirmed=False).count()
    )

    inactive = (
        EmailSubscription.objects.filter(is_active=False).count() +
        SMSSubscription.objects.filter(is_active=False).count()
    )

    # Format for chart
    status_data = {
        'labels': ['Active & Confirmed', 'Active & Unconfirmed', 'Inactive'],
        'values': [active_confirmed, active_unconfirmed, inactive]
    }

    # Get recent activity (last 20 subscribers from both email and SMS)
    recent_email = list(email_subscribers[:20])
    recent_sms = list(sms_subscribers[:20])

    # Combine and annotate with type
    recent_activity = []
    for sub in recent_email:
        recent_activity.append({
            'type': 'email',
            'contact': sub.email,
            'source': sub.source,
            'subscribed_at': sub.subscribed_at
        })
    for sub in recent_sms:
        recent_activity.append({
            'type': 'sms',
            'contact': sub.phone_number,
            'source': sub.source,
            'subscribed_at': sub.subscribed_at
        })

    # Sort by subscribed_at and take top 20
    recent_activity.sort(key=lambda x: x['subscribed_at'], reverse=True)
    recent_activity = recent_activity[:20]

    context = {
        'email_subscribers': email_subscribers,
        'sms_subscribers': sms_subscribers,
        'total_unique': total_unique,
        'new_24h': new_24h,
        'chart_data_7': json.dumps(chart_data_7),
        'chart_data_30': json.dumps(chart_data_30),
        'chart_data_90': json.dumps(chart_data_90),
        'chart_data_365': json.dumps(chart_data_365),
        'status_data': json.dumps(status_data),
        'recent_activity': recent_activity,
        'cst_time': timezone.now().astimezone(pytz.timezone('America/Chicago')),
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
    if request.method == 'POST' and request.POST.get('action') == 'send_campaign':
        campaign_id = request.POST.get('campaign_id')
        try:
            campaign = SMSCampaign.objects.get(id=campaign_id)
            if campaign.status in ['draft', 'scheduled']:
                result = send_campaign(campaign)
                if 'error' in result:
                    messages.error(request, f'Campaign failed: {result["error"]}')
                else:
                    messages.success(request, f'Campaign sent! Sent: {result["sent"]}, Failed: {result["failed"]}')
            else:
                messages.error(request, f'Campaign cannot be sent (status: {campaign.status})')
        except SMSCampaign.DoesNotExist:
            messages.error(request, 'Campaign not found')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')

        return redirect('admin_sms')

    # SMS Subscription metrics
    total_sms_subs = SMSSubscription.objects.count()
    active_sms_subs = SMSSubscription.objects.filter(is_active=True).count()
    confirmed_sms_subs = SMSSubscription.objects.filter(is_confirmed=True).count()
    recent_sms_subs_24h = SMSSubscription.objects.filter(subscribed_at__gte=last_24h).count()
    recent_sms_subs_7d = SMSSubscription.objects.filter(subscribed_at__gte=last_7d).count()

    sms_metrics = {
        'total': total_sms_subs,
        'active': active_sms_subs,
        'confirmed': confirmed_sms_subs,
        'recent_24h': recent_sms_subs_24h,
        'recent_7d': recent_sms_subs_7d,
        'active_rate': round((active_sms_subs / total_sms_subs * 100), 1) if total_sms_subs > 0 else 0,
    }

    # Templates
    templates = SMSTemplate.objects.all().order_by('-updated_at')
    total_templates = templates.count()
    active_templates = templates.filter(is_active=True).count()

    # Campaigns
    campaigns = SMSCampaign.objects.all().order_by('-created_at')[:10]
    total_campaigns = SMSCampaign.objects.count()

    campaign_stats = {
        'total': total_campaigns,
        'draft': SMSCampaign.objects.filter(status='draft').count(),
        'scheduled': SMSCampaign.objects.filter(status='scheduled').count(),
        'sent': SMSCampaign.objects.filter(status='sent').count(),
    }

    # Recent SMS logs
    recent_logs = SMSLog.objects.select_related('subscription', 'campaign', 'template').order_by('-sent_at')[:20]

    # SMS stats by status
    total_sms_sent = SMSLog.objects.count()
    sms_delivered = SMSLog.objects.filter(status='delivered').count()
    sms_failed = SMSLog.objects.filter(status='failed').count()
    sms_sent_24h = SMSLog.objects.filter(sent_at__gte=last_24h).count()

    sms_log_stats = {
        'total': total_sms_sent,
        'delivered': sms_delivered,
        'failed': sms_failed,
        'sent_24h': sms_sent_24h,
        'delivery_rate': round((sms_delivered / total_sms_sent * 100), 1) if total_sms_sent > 0 else 0,
    }

    # Recent subscribers
    recent_subscribers = SMSSubscription.objects.order_by('-subscribed_at')[:10]

    # Chart data for subscriber growth (last 30 days)
    subscriber_growth = []
    for i in range(30, -1, -1):
        date = (now - timedelta(days=i)).date()
        count = SMSSubscription.objects.filter(subscribed_at__date=date).count()
        subscriber_growth.append({
            'date': date.strftime('%m/%d'),
            'count': count
        })

    context = {
        'sms_metrics': sms_metrics,
        'templates': templates,
        'total_templates': total_templates,
        'active_templates': active_templates,
        'campaigns': campaigns,
        'campaign_stats': campaign_stats,
        'recent_logs': recent_logs,
        'sms_log_stats': sms_log_stats,
        'recent_subscribers': recent_subscribers,
        'subscriber_growth': subscriber_growth,
        'cst_time': timezone.now().astimezone(pytz.timezone('America/Chicago')),
    }

    return render(request, 'admin/sms_dashboard.html', context)


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
    if request.method == 'POST' and request.POST.get('action') == 'send_campaign':
        campaign_id = request.POST.get('campaign_id')
        try:
            campaign = EmailCampaign.objects.get(id=campaign_id)
            if campaign.status in ['draft', 'scheduled']:
                result = send_campaign(campaign)
                if 'error' in result:
                    messages.error(request, f'Campaign failed: {result["error"]}')
                else:
                    messages.success(request, f'Campaign sent! Sent: {result["sent"]}, Failed: {result["failed"]}')
            else:
                messages.error(request, f'Campaign cannot be sent (status: {campaign.status})')
        except EmailCampaign.DoesNotExist:
            messages.error(request, 'Campaign not found')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')

        return redirect('admin_email')

    # Email Subscription metrics
    total_email_subs = EmailSubscription.objects.count()
    active_email_subs = EmailSubscription.objects.filter(is_active=True).count()
    confirmed_email_subs = EmailSubscription.objects.filter(is_confirmed=True).count()
    recent_email_subs_24h = EmailSubscription.objects.filter(subscribed_at__gte=last_24h).count()
    recent_email_subs_7d = EmailSubscription.objects.filter(subscribed_at__gte=last_7d).count()

    email_metrics = {
        'total': total_email_subs,
        'active': active_email_subs,
        'confirmed': confirmed_email_subs,
        'recent_24h': recent_email_subs_24h,
        'recent_7d': recent_email_subs_7d,
        'active_rate': round((active_email_subs / total_email_subs * 100), 1) if total_email_subs > 0 else 0,
    }

    # Templates
    templates = EmailTemplate.objects.all().order_by('-updated_at')
    total_templates = templates.count()
    active_templates = templates.filter(is_active=True).count()

    # Campaigns
    campaigns = EmailCampaign.objects.all().order_by('-created_at')[:10]
    total_campaigns = EmailCampaign.objects.count()

    campaign_stats = {
        'total': total_campaigns,
        'draft': EmailCampaign.objects.filter(status='draft').count(),
        'scheduled': EmailCampaign.objects.filter(status='scheduled').count(),
        'sent': EmailCampaign.objects.filter(status='sent').count(),
    }

    # Recent email logs
    recent_logs = EmailLog.objects.select_related('subscription', 'campaign', 'template').order_by('-sent_at')[:20]

    # Email stats by status
    total_emails_sent = EmailLog.objects.count()
    emails_delivered = EmailLog.objects.filter(status='delivered').count()
    emails_failed = EmailLog.objects.filter(status='failed').count()
    emails_sent_24h = EmailLog.objects.filter(sent_at__gte=last_24h).count()

    email_log_stats = {
        'total': total_emails_sent,
        'delivered': emails_delivered,
        'failed': emails_failed,
        'sent_24h': emails_sent_24h,
        'delivery_rate': round((emails_delivered / total_emails_sent * 100), 1) if total_emails_sent > 0 else 0,
    }

    # Recent subscribers
    recent_subscribers = EmailSubscription.objects.order_by('-subscribed_at')[:10]

    # Chart data for subscriber growth (last 30 days)
    subscriber_growth = []
    for i in range(30, -1, -1):
        date = (now - timedelta(days=i)).date()
        count = EmailSubscription.objects.filter(subscribed_at__date=date).count()
        subscriber_growth.append({
            'date': date.strftime('%m/%d'),
            'count': count
        })

    context = {
        'email_metrics': email_metrics,
        'templates': templates,
        'total_templates': total_templates,
        'active_templates': active_templates,
        'campaigns': campaigns,
        'campaign_stats': campaign_stats,
        'recent_logs': recent_logs,
        'email_log_stats': email_log_stats,
        'recent_subscribers': recent_subscribers,
        'subscriber_growth': subscriber_growth,
        'cst_time': timezone.now().astimezone(pytz.timezone('America/Chicago')),
    }

    return render(request, 'admin/email_dashboard.html', context)


@staff_member_required
def sms_campaigns(request):
    """
    SMS Campaign management page with create/edit functionality.
    """
    # Handle create/edit
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            name = request.POST.get('name')
            template_id = request.POST.get('template')
            scheduled_at = request.POST.get('scheduled_at')
            notes = request.POST.get('notes', '')

            try:
                template = SMSTemplate.objects.get(id=template_id)
                campaign = SMSCampaign.objects.create(
                    name=name,
                    template=template,
                    scheduled_at=scheduled_at if scheduled_at else None,
                    status='scheduled' if scheduled_at else 'draft',
                    notes=notes,
                    created_by=request.user
                )
                messages.success(request, f'Campaign "{campaign.name}" created successfully!')
                return redirect('admin_sms_campaigns')
            except Exception as e:
                messages.error(request, f'Error creating campaign: {str(e)}')

        elif action == 'delete':
            campaign_id = request.POST.get('campaign_id')
            try:
                campaign = SMSCampaign.objects.get(id=campaign_id)
                campaign.delete()
                messages.success(request, 'Campaign deleted successfully!')
            except Exception as e:
                messages.error(request, f'Error deleting campaign: {str(e)}')
            return redirect('admin_sms_campaigns')

    # Get all campaigns
    campaigns = SMSCampaign.objects.all().order_by('-created_at')
    templates = SMSTemplate.objects.filter(is_active=True).order_by('name')

    context = {
        'campaigns': campaigns,
        'templates': templates,
        'cst_time': timezone.now().astimezone(pytz.timezone('America/Chicago')),
    }

    return render(request, 'admin/sms_campaigns.html', context)


@staff_member_required
def email_campaigns(request):
    """
    Email Campaign management page with create/edit functionality.
    """
    # Handle create/edit
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            name = request.POST.get('name')
            template_id = request.POST.get('template')
            scheduled_at = request.POST.get('scheduled_at')
            notes = request.POST.get('notes', '')

            try:
                template = EmailTemplate.objects.get(id=template_id)
                campaign = EmailCampaign.objects.create(
                    name=name,
                    template=template,
                    scheduled_at=scheduled_at if scheduled_at else None,
                    status='scheduled' if scheduled_at else 'draft',
                    notes=notes,
                    created_by=request.user
                )
                messages.success(request, f'Campaign "{campaign.name}" created successfully!')
                return redirect('admin_email_campaigns')
            except Exception as e:
                messages.error(request, f'Error creating campaign: {str(e)}')

        elif action == 'delete':
            campaign_id = request.POST.get('campaign_id')
            try:
                campaign = EmailCampaign.objects.get(id=campaign_id)
                campaign.delete()
                messages.success(request, 'Campaign deleted successfully!')
            except Exception as e:
                messages.error(request, f'Error deleting campaign: {str(e)}')
            return redirect('admin_email_campaigns')

    # Get all campaigns
    campaigns = EmailCampaign.objects.all().order_by('-created_at')
    templates = EmailTemplate.objects.filter(is_active=True).order_by('name')

    context = {
        'campaigns': campaigns,
        'templates': templates,
        'cst_time': timezone.now().astimezone(pytz.timezone('America/Chicago')),
    }

    return render(request, 'admin/email_campaigns.html', context)


@staff_member_required
def sms_templates(request):
    """
    SMS Template management page with create/edit functionality.
    """
    # Handle create/edit
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            name = request.POST.get('name')
            template_type = request.POST.get('template_type')
            auto_trigger = request.POST.get('auto_trigger')
            message_body = request.POST.get('message_body')

            try:
                template = SMSTemplate.objects.create(
                    name=name,
                    template_type=template_type,
                    auto_trigger=auto_trigger,
                    message_body=message_body,
                    created_by=request.user
                )
                messages.success(request, f'Template "{template.name}" created successfully!')
                return redirect('admin_sms_templates')
            except Exception as e:
                messages.error(request, f'Error creating template: {str(e)}')

        elif action == 'update':
            template_id = request.POST.get('template_id')
            try:
                template = SMSTemplate.objects.get(id=template_id)
                template.name = request.POST.get('name')
                template.template_type = request.POST.get('template_type')
                template.auto_trigger = request.POST.get('auto_trigger')
                template.message_body = request.POST.get('message_body')
                template.is_active = request.POST.get('is_active') == 'on'
                template.save()
                messages.success(request, f'Template "{template.name}" updated successfully!')
                return redirect('admin_sms_templates')
            except Exception as e:
                messages.error(request, f'Error updating template: {str(e)}')

        elif action == 'delete':
            template_id = request.POST.get('template_id')
            try:
                template = SMSTemplate.objects.get(id=template_id)
                template.delete()
                messages.success(request, 'Template deleted successfully!')
            except Exception as e:
                messages.error(request, f'Error deleting template: {str(e)}')
            return redirect('admin_sms_templates')

    # Get template to edit if specified
    edit_template = None
    template_id = request.GET.get('edit')
    if template_id:
        try:
            edit_template = SMSTemplate.objects.get(id=template_id)
        except SMSTemplate.DoesNotExist:
            messages.error(request, 'Template not found')

    # Get all templates
    templates = SMSTemplate.objects.all().order_by('-created_at')

    context = {
        'templates': templates,
        'edit_template': edit_template,
        'template_types': SMSTemplate.TEMPLATE_TYPES,
        'trigger_types': SMSTemplate.TRIGGER_TYPES,
        'cst_time': timezone.now().astimezone(pytz.timezone('America/Chicago')),
    }

    return render(request, 'admin/sms_templates.html', context)


@staff_member_required
def email_templates(request):
    """
    Email Template management page with create/edit functionality.
    """
    # Handle create/edit
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            name = request.POST.get('name')
            template_type = request.POST.get('template_type')
            auto_trigger = request.POST.get('auto_trigger')
            subject = request.POST.get('subject')
            html_body = request.POST.get('html_body')
            text_body = request.POST.get('text_body', '')

            try:
                template = EmailTemplate.objects.create(
                    name=name,
                    template_type=template_type,
                    auto_trigger=auto_trigger,
                    subject=subject,
                    html_body=html_body,
                    text_body=text_body,
                    created_by=request.user
                )
                messages.success(request, f'Template "{template.name}" created successfully!')
                return redirect('admin_email_templates')
            except Exception as e:
                messages.error(request, f'Error creating template: {str(e)}')

        elif action == 'update':
            template_id = request.POST.get('template_id')
            try:
                template = EmailTemplate.objects.get(id=template_id)
                template.name = request.POST.get('name')
                template.template_type = request.POST.get('template_type')
                template.auto_trigger = request.POST.get('auto_trigger')
                template.subject = request.POST.get('subject')
                template.html_body = request.POST.get('html_body')
                template.text_body = request.POST.get('text_body', '')
                template.is_active = request.POST.get('is_active') == 'on'
                template.save()
                messages.success(request, f'Template "{template.name}" updated successfully!')
                return redirect('admin_email_templates')
            except Exception as e:
                messages.error(request, f'Error updating template: {str(e)}')

        elif action == 'delete':
            template_id = request.POST.get('template_id')
            try:
                template = EmailTemplate.objects.get(id=template_id)
                template.delete()
                messages.success(request, 'Template deleted successfully!')
            except Exception as e:
                messages.error(request, f'Error deleting template: {str(e)}')
            return redirect('admin_email_templates')

    # Get template to edit if specified
    edit_template = None
    template_id = request.GET.get('edit')
    if template_id:
        try:
            edit_template = EmailTemplate.objects.get(id=template_id)
        except EmailTemplate.DoesNotExist:
            messages.error(request, 'Template not found')

    # Get all templates
    templates = EmailTemplate.objects.all().order_by('-created_at')

    context = {
        'templates': templates,
        'edit_template': edit_template,
        'template_types': EmailTemplate.TEMPLATE_TYPES,
        'trigger_types': EmailTemplate.TRIGGER_TYPES,
        'cst_time': timezone.now().astimezone(pytz.timezone('America/Chicago')),
    }

    return render(request, 'admin/email_templates.html', context)


@staff_member_required
def homepage_settings(request):
    """
    Homepage settings management page for hero image, title, and subtitle.
    """
    site_settings = SiteSettings.load()

    if request.method == 'POST':
        # Handle image removal
        if request.POST.get('remove_image') == 'true':
            if site_settings.hero_image:
                site_settings.hero_image.delete(save=False)
                site_settings.hero_image = None
                site_settings.save()
                messages.success(request, 'Hero image removed successfully!')
                return redirect('admin_homepage')

        # Handle hero image upload
        if 'hero_image' in request.FILES:
            site_settings.hero_image = request.FILES['hero_image']

        # Update text fields
        site_settings.hero_title = request.POST.get('hero_title', site_settings.hero_title)
        site_settings.hero_subtitle = request.POST.get('hero_subtitle', site_settings.hero_subtitle)
        site_settings.save()

        messages.success(request, 'Homepage settings updated successfully!')
        return redirect('admin_homepage')

    context = {
        'site_settings': site_settings,
        'cst_time': timezone.now().astimezone(pytz.timezone('America/Chicago')),
    }

    return render(request, 'admin/homepage_settings.html', context)


@staff_member_required
def visitors_dashboard(request):
    """
    Visitor analytics dashboard showing page views, traffic sources, and device stats.
    """
    from django.db.models import Count, Avg, Q
    from shop.models import PageView, VisitorSession

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)
    last_30min = now - timedelta(minutes=30)

    # Quick stats
    stats = {
        'visits_today': VisitorSession.objects.filter(first_seen__gte=today_start).count(),
        'page_views_today': PageView.objects.filter(viewed_at__gte=today_start).count(),
        'active_sessions': VisitorSession.objects.filter(last_seen__gte=last_30min).count(),
        'visits_30d': VisitorSession.objects.filter(first_seen__gte=last_30d).count(),
    }

    # Average pages per session
    avg_pages = VisitorSession.objects.filter(first_seen__gte=last_30d).aggregate(
        avg=Avg('page_views')
    )
    stats['avg_pages_per_session'] = avg_pages['avg'] or 0

    # Mobile percentage
    total_visits_30d = stats['visits_30d']
    if total_visits_30d > 0:
        mobile_visits = VisitorSession.objects.filter(
            first_seen__gte=last_30d,
            device_type__in=['mobile', 'tablet']
        ).count()
        stats['mobile_percent'] = (mobile_visits / total_visits_30d) * 100
    else:
        stats['mobile_percent'] = 0

    # Page views for last 7 days
    page_views_7d = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        count = PageView.objects.filter(
            viewed_at__gte=day_start,
            viewed_at__lt=day_end
        ).count()
        page_views_7d.append({
            'date': day.strftime('%b %d'),
            'count': count
        })

    # Top countries
    top_countries = VisitorSession.objects.filter(
        first_seen__gte=last_30d
    ).exclude(country='').values('country', 'country_name').annotate(
        count=Count('id')
    ).order_by('-count')[:10]

    # Top cities
    top_cities = VisitorSession.objects.filter(
        first_seen__gte=last_30d
    ).exclude(city='').values('city', 'region', 'country').annotate(
        count=Count('id')
    ).order_by('-count')[:10]

    # Top referrers
    top_referrers = PageView.objects.filter(
        viewed_at__gte=last_30d
    ).values('referrer_domain').annotate(
        count=Count('id')
    ).order_by('-count')[:10]

    # Device breakdown
    device_stats = VisitorSession.objects.filter(
        first_seen__gte=last_30d
    ).values('device_type').annotate(
        count=Count('id')
    ).order_by('-count')

    import json

    device_labels = [d['device_type'].capitalize() for d in device_stats]
    device_counts = [d['count'] for d in device_stats]

    # Top pages
    top_pages = PageView.objects.filter(
        viewed_at__gte=last_30d
    ).values('path').annotate(
        views=Count('id'),
        unique_visitors=Count('session_id', distinct=True),
        avg_time=Avg('response_time_ms')
    ).order_by('-views')[:10]

    # Recent visitors
    recent_views = PageView.objects.all()[:20]

    context = {
        'stats': stats,
        'page_views_7d': page_views_7d,
        'top_countries': top_countries,
        'top_cities': top_cities,
        'top_referrers': top_referrers,
        'device_labels': json.dumps(device_labels),
        'device_counts': json.dumps(device_counts),
        'top_pages': top_pages,
        'recent_views': recent_views,
        'cst_time': timezone.now().astimezone(pytz.timezone('America/Chicago')),
    }

    return render(request, 'admin/visitors.html', context)


@staff_member_required
def all_campaigns(request):
    """
    Unified view showing both email and SMS campaigns together.
    """
    from shop.models import EmailCampaign, SMSCampaign

    # Get all email campaigns
    email_campaigns = EmailCampaign.objects.all().select_related('template')
    email_list = []
    for campaign in email_campaigns:
        email_list.append({
            'id': campaign.id,
            'type': 'email',
            'name': campaign.name,
            'template': campaign.template,
            'status': campaign.status,
            'get_status_display': campaign.get_status_display(),
            'scheduled_at': campaign.scheduled_at,
            'total_recipients': campaign.total_recipients,
            'sent_count': campaign.sent_count,
            'created_at': campaign.created_at,
        })

    # Get all SMS campaigns
    sms_campaigns = SMSCampaign.objects.all().select_related('template')
    sms_list = []
    for campaign in sms_campaigns:
        sms_list.append({
            'id': campaign.id,
            'type': 'sms',
            'name': campaign.name,
            'template': campaign.template,
            'status': campaign.status,
            'get_status_display': campaign.get_status_display(),
            'scheduled_at': campaign.scheduled_at,
            'total_recipients': campaign.total_recipients,
            'sent_count': campaign.sent_count,
            'created_at': campaign.created_at,
        })

    # Combine and sort by created_at
    all_campaigns_list = email_list + sms_list
    all_campaigns_list.sort(key=lambda x: x['created_at'], reverse=True)

    context = {
        'campaigns': all_campaigns_list,
        'cst_time': timezone.now().astimezone(pytz.timezone('America/Chicago')),
    }

    return render(request, 'admin/all_campaigns.html', context)


@staff_member_required
def campaign_create(request):
    """
    Create and manage unified campaigns containing multiple scheduled email/SMS messages.
    Example: "Fall Sale 2025" campaign with welcome email, follow-up SMS, reminder email.
    """
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_campaign':
            name = request.POST.get('name')
            description = request.POST.get('description', '')
            target_group = request.POST.get('target_group', '')
            active_from = request.POST.get('active_from')
            active_until = request.POST.get('active_until')

            try:
                campaign = Campaign.objects.create(
                    name=name,
                    description=description,
                    target_group=target_group,
                    active_from=active_from if active_from else None,
                    active_until=active_until if active_until else None,
                    created_by=request.user
                )
                messages.success(request, f'Campaign "{campaign.name}" created successfully!')
                return redirect('admin_campaign_edit', campaign_id=campaign.id)
            except Exception as e:
                messages.error(request, f'Error creating campaign: {str(e)}')

    # Get all email and SMS templates
    email_templates = EmailTemplate.objects.filter(is_active=True).order_by('name')
    sms_templates = SMSTemplate.objects.filter(is_active=True).order_by('name')

    context = {
        'email_templates': email_templates,
        'sms_templates': sms_templates,
        'cst_time': timezone.now().astimezone(pytz.timezone('America/Chicago')),
    }

    return render(request, 'admin/campaign_create.html', context)


@staff_member_required
def campaign_edit(request, campaign_id):
    """
    Edit campaign and manage its messages.
    """
    try:
        campaign = Campaign.objects.get(id=campaign_id)
    except Campaign.DoesNotExist:
        messages.error(request, 'Campaign not found')
        return redirect('admin_campaigns_list')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_campaign':
            campaign.name = request.POST.get('name')
            campaign.description = request.POST.get('description', '')
            campaign.target_group = request.POST.get('target_group', '')

            active_from = request.POST.get('active_from')
            active_until = request.POST.get('active_until')
            campaign.active_from = active_from if active_from else None
            campaign.active_until = active_until if active_until else None

            campaign.save()
            messages.success(request, f'Campaign "{campaign.name}" updated successfully!')
            return redirect('admin_campaign_edit', campaign_id=campaign.id)

        elif action == 'add_message':
            name = request.POST.get('message_name')
            message_type = request.POST.get('message_type')
            trigger_type = request.POST.get('trigger_type')
            order = request.POST.get('order', 0)
            custom_subject = request.POST.get('custom_subject', '')
            custom_content = request.POST.get('custom_content', '')

            # Get template if specified
            email_template_id = request.POST.get('email_template')
            sms_template_id = request.POST.get('sms_template')

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

                if message_type == 'email' and email_template_id:
                    message.email_template = EmailTemplate.objects.get(id=email_template_id)
                elif message_type == 'sms' and sms_template_id:
                    message.sms_template = SMSTemplate.objects.get(id=sms_template_id)

                # Handle delay settings
                if trigger_type == 'delay':
                    message.delay_days = int(request.POST.get('delay_days', 0))
                    message.delay_hours = int(request.POST.get('delay_hours', 0))
                elif trigger_type == 'specific_date':
                    scheduled_date = request.POST.get('scheduled_date')
                    if scheduled_date:
                        message.scheduled_date = scheduled_date

                message.save()
                messages.success(request, f'Message "{message.name}" added successfully!')
                return redirect('admin_campaign_edit', campaign_id=campaign.id)
            except Exception as e:
                messages.error(request, f'Error adding message: {str(e)}')

        elif action == 'delete_message':
            message_id = request.POST.get('message_id')
            try:
                message = CampaignMessage.objects.get(id=message_id, campaign=campaign)
                message.delete()
                messages.success(request, 'Message deleted successfully!')
            except Exception as e:
                messages.error(request, f'Error deleting message: {str(e)}')
            return redirect('admin_campaign_edit', campaign_id=campaign.id)

    # Get campaign messages ordered by sequence
    messages_list = campaign.messages.all().order_by('order', 'created_at')

    # Get templates
    email_templates = EmailTemplate.objects.filter(is_active=True).order_by('name')
    sms_templates = SMSTemplate.objects.filter(is_active=True).order_by('name')

    context = {
        'campaign': campaign,
        'messages_list': messages_list,
        'email_templates': email_templates,
        'sms_templates': sms_templates,
        'cst_time': timezone.now().astimezone(pytz.timezone('America/Chicago')),
    }

    return render(request, 'admin/campaign_edit.html', context)


@staff_member_required
def products_dashboard(request):
    """
    Products management dashboard.
    """
    from shop.models import Product, ProductVariant
    from django.db.models import Count, Sum, Q

    # Handle product actions
    if request.method == 'POST':
        from django.http import JsonResponse
        action = request.POST.get('action')

        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"POST action received: {action}")

        if action == 'toggle_active':
            from django.http import JsonResponse
            product_id = request.POST.get('product_id')
            try:
                product = Product.objects.get(id=product_id)
                product.is_active = not product.is_active
                product.save()
                return JsonResponse({'success': True, 'is_active': product.is_active})
            except Product.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Product not found'})

        elif action == 'update_price':
            from django.http import JsonResponse
            product_id = request.POST.get('product_id')
            new_price = request.POST.get('price')
            try:
                product = Product.objects.get(id=product_id)
                product.base_price = new_price
                product.save()
                return JsonResponse({'success': True})
            except Product.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Product not found'})
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})

        elif action == 'update_product':
            from django.http import JsonResponse
            from shop.models import Category
            product_id = request.POST.get('product_id')
            try:
                product = Product.objects.get(id=product_id)
                product.name = request.POST.get('name')
                product.slug = request.POST.get('slug')

                # Update category - try to find Category object by slug, fallback to legacy
                category_slug = request.POST.get('category')
                if category_slug:
                    try:
                        category_obj = Category.objects.get(slug=category_slug)
                        product.category_obj = category_obj
                    except Category.DoesNotExist:
                        # Fallback to legacy category field
                        product.category_legacy = category_slug

                product.description = request.POST.get('description')
                product.base_price = request.POST.get('base_price')
                product.featured = request.POST.get('featured') == 'true'
                product.save()
                return JsonResponse({'success': True})
            except Product.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Product not found'})
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})

        elif action == 'get_sizes_colors_materials':
            from django.http import JsonResponse
            from shop.models import Size, Color, Material

            sizes = list(Size.objects.all().values('id', 'code', 'label'))
            colors = list(Color.objects.all().values('id', 'name'))
            materials = list(Material.objects.all().values('id', 'name'))

            return JsonResponse({
                'success': True,
                'sizes': sizes,
                'colors': colors,
                'materials': materials
            })

        elif action == 'get_product_category_attributes':
            from django.http import JsonResponse
            product_id = request.POST.get('product_id')
            try:
                product = Product.objects.get(id=product_id)
                category = product.category_obj

                if not category:
                    return JsonResponse({
                        'success': False,
                        'error': 'Product has no category assigned'
                    })

                return JsonResponse({
                    'success': True,
                    'category_name': category.name,
                    'uses_size': category.uses_size,
                    'uses_color': category.uses_color,
                    'uses_material': category.uses_material,
                    'custom_attributes': category.custom_attributes or [],
                    'common_fields': category.common_fields or []
                })
            except Product.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Product not found'})

        elif action == 'get_variants':
            from django.http import JsonResponse
            product_id = request.POST.get('product_id')
            try:
                product = Product.objects.get(id=product_id)
                variants = product.variants.all().select_related('size', 'color', 'material')

                variants_data = [{
                    'id': v.id,
                    'sku': v.sku,
                    'size': str(v.size),
                    'size_id': v.size.id,
                    'color': str(v.color),
                    'color_id': v.color.id,
                    'material': str(v.material) if v.material else None,
                    'material_id': v.material.id if v.material else None,
                    'stock_quantity': v.stock_quantity,
                    'price': str(v.price),
                    'is_active': v.is_active,
                    'images': v.images if hasattr(v, 'images') else [],
                    'custom_fields': v.custom_fields if hasattr(v, 'custom_fields') else {},
                } for v in variants]

                return JsonResponse({
                    'success': True,
                    'variants': variants_data
                })
            except Product.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Product not found'})

        elif action == 'add_variant':
            from django.http import JsonResponse
            import json
            product_id = request.POST.get('product_id')
            size_id = request.POST.get('size_id')
            color_id = request.POST.get('color_id')
            material_id = request.POST.get('material_id')
            sku = request.POST.get('sku', '')
            stock_quantity = request.POST.get('stock_quantity', 0)
            price = request.POST.get('price')
            images_json = request.POST.get('images', '[]')
            custom_fields_json = request.POST.get('custom_fields', '{}')

            try:
                from shop.models import Size, Color, Material
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
                    product=product,
                    size=size,
                    color=color,
                    material=material
                ).first()

                if existing:
                    parts = [str(size), str(color)]
                    if material:
                        parts.append(str(material))
                    return JsonResponse({
                        'success': False,
                        'error': f'Variant {" - ".join(parts)} already exists'
                    })

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
                    is_active=True
                )

                return JsonResponse({'success': True})
            except Product.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Product not found'})
            except Size.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Size not found'})
            except Color.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Color not found'})
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})

        elif action == 'update_variant_price':
            from django.http import JsonResponse
            variant_id = request.POST.get('variant_id')
            new_price = request.POST.get('price')

            try:
                variant = ProductVariant.objects.get(id=variant_id)
                variant.price = new_price
                variant.save()
                return JsonResponse({'success': True})
            except ProductVariant.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Variant not found'})
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})

        elif action == 'toggle_variant_active':
            from django.http import JsonResponse
            variant_id = request.POST.get('variant_id')

            try:
                variant = ProductVariant.objects.get(id=variant_id)
                variant.is_active = not variant.is_active
                variant.save()
                return JsonResponse({'success': True, 'is_active': variant.is_active})
            except ProductVariant.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Variant not found'})

        elif action == 'delete_variant':
            from django.http import JsonResponse
            variant_id = request.POST.get('variant_id')

            try:
                variant = ProductVariant.objects.get(id=variant_id)
                variant.delete()
                return JsonResponse({'success': True})
            except ProductVariant.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Variant not found'})
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})

        # If we got here, the action was not recognized
        return JsonResponse({'success': False, 'error': f'Unknown action: {action}'})

    # Get all products with variant counts
    products = Product.objects.all().order_by('-is_active', 'name')

    # Enrich products with variant data
    products_data = []
    for product in products:
        variant_count = product.variants.count()
        total_stock = product.variants.aggregate(total=Sum('stock_quantity'))['total'] or 0
        active_variants = product.variants.filter(is_active=True).count()

        # Get category slug for editing
        category_slug = ''
        if product.category_obj:
            category_slug = product.category_obj.slug
        elif product.category_legacy:
            category_slug = product.category_legacy

        products_data.append({
            'id': product.id,
            'name': product.name,
            'slug': product.slug,
            'category': product.category_obj.name if product.category_obj else (product.category_legacy or 'Uncategorized'),
            'category_slug': category_slug,
            'description': product.description,
            'base_price': product.base_price,
            'is_active': product.is_active,
            'featured': product.featured,
            'variant_count': variant_count,
            'total_stock': total_stock,
            'active_variants': active_variants,
        })

    # Stats
    total_products = products.count()
    active_products = products.filter(is_active=True).count()
    total_variants = ProductVariant.objects.count()
    total_stock = ProductVariant.objects.aggregate(total=Sum('stock_quantity'))['total'] or 0
    low_stock_count = ProductVariant.objects.filter(stock_quantity__lt=10, stock_quantity__gt=0).count()
    out_of_stock_count = ProductVariant.objects.filter(stock_quantity=0).count()

    # Get all categories for the dropdown
    from shop.models import Category
    categories = Category.objects.all().order_by('name')

    context = {
        'products': products_data,
        'categories': categories,
        'total_products': total_products,
        'active_products': active_products,
        'total_variants': total_variants,
        'total_stock': total_stock,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
        'cst_time': timezone.now().astimezone(pytz.timezone('America/Chicago')),
    }

    return render(request, 'admin/products_dashboard.html', context)


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

    context = {
        'product': product,
    }

    return render(request, 'admin/product_preview.html', context)


@staff_member_required
def categories_dashboard(request):
    """
    Categories management dashboard.
    """
    from shop.models import Category
    from django.http import JsonResponse

    # Handle category actions
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_category':
            import json
            try:
                name = request.POST.get('name')
                slug = request.POST.get('slug')
                description = request.POST.get('description', '')
                uses_size = request.POST.get('uses_size') == 'true'
                uses_color = request.POST.get('uses_color') == 'true'
                uses_material = request.POST.get('uses_material') == 'true'
                custom_attributes = json.loads(request.POST.get('custom_attributes', '[]'))
                common_fields = json.loads(request.POST.get('common_fields', '[]'))

                category = Category.objects.create(
                    name=name,
                    slug=slug,
                    description=description,
                    uses_size=uses_size,
                    uses_color=uses_color,
                    uses_material=uses_material,
                    custom_attributes=custom_attributes,
                    common_fields=common_fields
                )

                return JsonResponse({'success': True, 'category_id': category.id})
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})

        elif action == 'update_category':
            import json
            try:
                category_id = request.POST.get('category_id')
                category = Category.objects.get(id=category_id)

                category.name = request.POST.get('name')
                category.slug = request.POST.get('slug')
                category.description = request.POST.get('description', '')
                category.uses_size = request.POST.get('uses_size') == 'true'
                category.uses_color = request.POST.get('uses_color') == 'true'
                category.uses_material = request.POST.get('uses_material') == 'true'
                category.custom_attributes = json.loads(request.POST.get('custom_attributes', '[]'))
                category.common_fields = json.loads(request.POST.get('common_fields', '[]'))
                category.save()

                return JsonResponse({'success': True})
            except Category.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Category not found'})
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})

        elif action == 'delete_category':
            try:
                category_id = request.POST.get('category_id')
                category = Category.objects.get(id=category_id)

                # Check if category has products
                if category.products.exists():
                    return JsonResponse({
                        'success': False,
                        'error': f'Cannot delete category with {category.products.count()} products. Reassign or delete products first.'
                    })

                category.delete()
                return JsonResponse({'success': True})
            except Category.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Category not found'})
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})

    # Get all categories with product counts
    categories = Category.objects.all().order_by('name')
    categories_data = []

    for category in categories:
        categories_data.append({
            'id': category.id,
            'name': category.name,
            'slug': category.slug,
            'description': category.description,
            'uses_size': category.uses_size,
            'uses_color': category.uses_color,
            'uses_material': category.uses_material,
            'custom_attributes': category.custom_attributes,
            'common_fields': category.common_fields,
            'product_count': category.products.count(),
        })

    import json
    context = {
        'categories': categories_data,
        'categories_json': json.dumps(categories_data),
        'total_categories': categories.count(),
        'cst_time': timezone.now().astimezone(pytz.timezone('America/Chicago')),
    }

    return render(request, 'admin/categories_dashboard.html', context)


@staff_member_required
def discounts_dashboard(request):
    """
    Discounts and deals management dashboard.
    """
    from shop.models import Discount
    from django.http import JsonResponse

    # Handle discount actions
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'toggle_discount':
            discount_id = request.POST.get('discount_id')
            try:
                discount = Discount.objects.get(id=discount_id)
                discount.is_active = not discount.is_active
                discount.save()
                return JsonResponse({'success': True, 'is_active': discount.is_active})
            except Discount.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Discount not found'})

        elif action == 'create_discount':
            try:
                discount = Discount(
                    name=request.POST.get('name'),
                    code=request.POST.get('code'),
                    discount_type=request.POST.get('discount_type'),
                    value=request.POST.get('value'),
                    min_purchase_amount=request.POST.get('min_purchase_amount') or None,
                    max_uses=request.POST.get('max_uses') or None,
                    valid_from=request.POST.get('valid_from'),
                    valid_until=request.POST.get('valid_until') or None,
                    applies_to_all=request.POST.get('applies_to_all') == 'true',
                    is_active=True
                )
                discount.save()
                return JsonResponse({'success': True})
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})

    # Get all discounts
    discounts = Discount.objects.all().order_by('-created_at')

    # Stats
    active_discounts = discounts.filter(is_active=True).count()
    total_uses = sum(d.times_used for d in discounts)

    # Get valid discounts
    from django.utils import timezone
    now = timezone.now()
    valid_discounts = [d for d in discounts if d.is_valid]

    context = {
        'discounts': discounts,
        'active_discounts': active_discounts,
        'total_uses': total_uses,
        'valid_discounts_count': len(valid_discounts),
        'cst_time': timezone.now().astimezone(pytz.timezone('America/Chicago')),
    }

    return render(request, 'admin/discounts_dashboard.html', context)


@staff_member_required
def campaigns_list(request):
    """
    List all unified campaigns.
    """
    # Handle GET request for fetching message data
    if request.method == 'GET' and request.GET.get('action') == 'get_message':
        from django.http import JsonResponse
        try:
            message_id = request.GET.get('message_id')
            message = CampaignMessage.objects.get(id=message_id)

            return JsonResponse({
                'success': True,
                'message': {
                    'id': message.id,
                    'message_type': message.message_type,
                    'custom_subject': message.custom_subject or '',
                    'custom_content': message.custom_content or '',
                    'media_urls': message.media_urls or '',
                    'notes': message.notes or '',
                    'send_mode': message.send_mode or 'auto',
                }
            })
        except CampaignMessage.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Message not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    if request.method == 'POST':
        action = request.POST.get('action')
        campaign_id = request.POST.get('campaign_id')

        if action == 'delete':
            try:
                campaign = Campaign.objects.get(id=campaign_id)
                campaign.delete()
                messages.success(request, 'Campaign deleted successfully!')
            except Exception as e:
                messages.error(request, f'Error deleting campaign: {str(e)}')
            return redirect('admin_campaigns_list')

        elif action == 'update_window':
            try:
                from django.http import JsonResponse
                campaign = Campaign.objects.get(id=campaign_id)

                active_from = request.POST.get('active_from')
                active_until = request.POST.get('active_until')

                campaign.active_from = active_from if active_from else None
                campaign.active_until = active_until if active_until else None
                campaign.save()

                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True})
                else:
                    messages.success(request, 'Operating window updated successfully!')
                    return redirect('admin_campaigns_list')
            except Exception as e:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': str(e)})
                else:
                    messages.error(request, f'Error updating operating window: {str(e)}')
                    return redirect('admin_campaigns_list')

        elif action == 'add_message':
            try:
                from django.db.models import Max
                from datetime import datetime
                campaign = Campaign.objects.get(id=campaign_id)
                message_type = request.POST.get('message_type')
                scheduled_date_str = request.POST.get('scheduled_date')

                # Get next order number
                max_order_result = campaign.messages.aggregate(max_order=Max('order'))
                max_order = max_order_result['max_order'] if max_order_result['max_order'] is not None else 0
                next_order = max_order + 1

                # Parse scheduled date and time if provided
                scheduled_date = None
                if scheduled_date_str:
                    try:
                        # Parse date string (format: YYYY-MM-DD)
                        scheduled_date = timezone.datetime.strptime(scheduled_date_str, '%Y-%m-%d')

                        # Add time component if provided
                        scheduled_time_str = request.POST.get('scheduled_time')
                        if scheduled_time_str:
                            try:
                                time_parts = scheduled_time_str.split(':')
                                scheduled_date = scheduled_date.replace(
                                    hour=int(time_parts[0]),
                                    minute=int(time_parts[1]) if len(time_parts) > 1 else 0
                                )
                            except (ValueError, IndexError):
                                pass

                        scheduled_date = timezone.make_aware(scheduled_date)
                    except ValueError:
                        pass

                # Get universal send_mode (fallback to type-specific if not provided)
                send_mode = request.POST.get('send_mode', 'auto')

                # Create message based on type
                if message_type == 'email':
                    subject = request.POST.get('email_subject', '').strip()
                    body = request.POST.get('email_body', '').strip()
                    recipient_group = request.POST.get('email_recipient', 'all')
                    # Use type-specific send_mode if provided, otherwise use universal
                    send_mode = request.POST.get('email_send_mode', send_mode)

                    if not subject or not body:
                        messages.error(request, 'Email subject and body are required!')
                        return redirect('admin_campaigns_list')

                    # Map recipient group to display name
                    recipient_display = {
                        'all': 'All Email Subscribers',
                        'new_customers': 'New Customers (Last 30 days)',
                        'vip': 'VIP Customers',
                        'inactive': 'Inactive Customers',
                        'custom': 'Custom Selection'
                    }.get(recipient_group, 'All Email Subscribers')

                    # Set status based on send mode
                    msg_status = 'draft' if send_mode == 'draft' else 'pending'

                    message = CampaignMessage.objects.create(
                        campaign=campaign,
                        message_type='email',
                        name=f"{subject} → {recipient_display}",
                        custom_subject=subject,
                        custom_content=body,
                        order=next_order,
                        status=msg_status,
                        send_mode=send_mode,
                        trigger_type='specific_date' if scheduled_date else 'immediate',
                        scheduled_date=scheduled_date
                    )

                    messages.success(request, f'Email message "{subject}" added to campaign for {recipient_display}!')

                elif message_type == 'sms':
                    sms_message = request.POST.get('sms_message', '').strip()
                    recipient_group = request.POST.get('sms_to', 'all')
                    # Use type-specific send_mode if provided, otherwise use universal
                    send_mode = request.POST.get('sms_send_mode', send_mode)

                    if not sms_message:
                        messages.error(request, 'SMS message is required!')
                        return redirect('admin_campaigns_list')

                    # Map recipient group to display name
                    recipient_display = {
                        'all': 'All SMS Subscribers',
                        'new_customers': 'New Customers (Last 30 days)',
                        'vip': 'VIP Customers',
                        'inactive': 'Inactive Customers',
                        'custom': 'Custom Selection'
                    }.get(recipient_group, 'All SMS Subscribers')

                    # Set status based on send mode
                    msg_status = 'draft' if send_mode == 'draft' else 'pending'

                    message = CampaignMessage.objects.create(
                        campaign=campaign,
                        message_type='sms',
                        name=f"{sms_message[:30]}... → {recipient_display}" if len(sms_message) > 30 else f"{sms_message} → {recipient_display}",
                        custom_content=sms_message,
                        order=next_order,
                        status=msg_status,
                        send_mode=send_mode,
                        trigger_type='specific_date' if scheduled_date else 'immediate',
                        scheduled_date=scheduled_date
                    )

                    messages.success(request, f'SMS message added to campaign for {recipient_display}!')

                elif message_type == 'instagram':
                    caption = request.POST.get('instagram_caption', '').strip()
                    media_urls = request.POST.get('instagram_media', '').strip()
                    notes = request.POST.get('instagram_notes', '').strip()

                    # Set status based on send mode
                    msg_status = 'draft' if send_mode == 'draft' else 'pending'

                    message = CampaignMessage.objects.create(
                        campaign=campaign,
                        message_type='instagram',
                        name=f"Instagram: {caption[:40]}..." if len(caption) > 40 else f"Instagram: {caption}" if caption else "Instagram Post",
                        custom_subject=caption,  # Caption
                        custom_content=notes,  # Notes
                        media_urls=media_urls,
                        notes=notes,
                        order=next_order,
                        status=msg_status,
                        send_mode=send_mode,
                        trigger_type='specific_date' if scheduled_date else 'immediate',
                        scheduled_date=scheduled_date
                    )

                    messages.success(request, 'Instagram post added to campaign!')

                elif message_type == 'tiktok':
                    caption = request.POST.get('tiktok_caption', '').strip()
                    media_url = request.POST.get('tiktok_media', '').strip()
                    notes = request.POST.get('tiktok_notes', '').strip()

                    message = CampaignMessage.objects.create(
                        campaign=campaign,
                        message_type='tiktok',
                        name=f"TikTok: {caption[:40]}..." if len(caption) > 40 else f"TikTok: {caption}" if caption else "TikTok Video",
                        custom_subject=caption,
                        custom_content=notes,
                        media_urls=media_url,
                        notes=notes,
                        order=next_order,
                        status='draft',
                        trigger_type='specific_date' if scheduled_date else 'immediate',
                        scheduled_date=scheduled_date
                    )

                    messages.success(request, 'TikTok video added to campaign!')

                elif message_type == 'snapchat':
                    caption = request.POST.get('snapchat_caption', '').strip()
                    media_url = request.POST.get('snapchat_media', '').strip()
                    notes = request.POST.get('snapchat_notes', '').strip()

                    message = CampaignMessage.objects.create(
                        campaign=campaign,
                        message_type='snapchat',
                        name=f"Snapchat: {caption[:40]}..." if len(caption) > 40 else f"Snapchat: {caption}" if caption else "Snapchat Story",
                        custom_subject=caption,
                        custom_content=notes,
                        media_urls=media_url,
                        notes=notes,
                        order=next_order,
                        status='draft',
                        trigger_type='specific_date' if scheduled_date else 'immediate',
                        scheduled_date=scheduled_date
                    )

                    messages.success(request, 'Snapchat story added to campaign!')

                elif message_type == 'youtube':
                    title = request.POST.get('youtube_title', '').strip()
                    video_url = request.POST.get('youtube_url', '').strip()
                    description = request.POST.get('youtube_description', '').strip()

                    message = CampaignMessage.objects.create(
                        campaign=campaign,
                        message_type='youtube',
                        name=f"YouTube: {title[:40]}..." if len(title) > 40 else f"YouTube: {title}" if title else "YouTube Video",
                        custom_subject=title,
                        custom_content=description,
                        media_urls=video_url,
                        notes=description,
                        order=next_order,
                        status='draft',
                        trigger_type='specific_date' if scheduled_date else 'immediate',
                        scheduled_date=scheduled_date
                    )

                    messages.success(request, 'YouTube video added to campaign!')

                elif message_type == 'promotion':
                    from shop.models import Discount, Product
                    from decimal import Decimal

                    promo_title = request.POST.get('promotion_title', '').strip()
                    promo_type = request.POST.get('promotion_type', 'public').strip()
                    promo_code = request.POST.get('promotion_code', '').strip().upper()
                    discount_type = request.POST.get('promotion_discount_type', 'percentage').strip()
                    discount_value = request.POST.get('promotion_discount_value', '').strip()
                    product_ids = request.POST.getlist('promotion_products')
                    promo_details = request.POST.get('promotion_details', '').strip()

                    if not promo_title:
                        messages.error(request, 'Promotion title is required!')
                        return redirect('admin_campaigns_list')

                    # Validate discount amount for all promotions (except BOGO and Free Shipping)
                    if discount_type not in ['bogo', 'free_shipping'] and not discount_value:
                        messages.error(request, 'Discount amount is required!')
                        return redirect('admin_campaigns_list')

                    # Validate private promotion requirements
                    if promo_type == 'private':
                        if not promo_code:
                            messages.error(request, 'Discount code is required for private promotions!')
                            return redirect('admin_campaigns_list')

                        # Check code uniqueness
                        if Discount.objects.filter(code=promo_code).exists():
                            messages.error(request, f'Discount code "{promo_code}" already exists! Please use a different code.')
                            return redirect('admin_campaigns_list')

                    # Build notes with promotion type and code info
                    notes_parts = []
                    if promo_type == 'public':
                        notes_parts.append('Type: Public Sale (No code required)')
                    else:
                        notes_parts.append('Type: Private/Code Only')
                        if promo_code:
                            notes_parts.append(f'Code: {promo_code}')

                    if promo_details:
                        notes_parts.append(f'\nDetails: {promo_details}')

                    combined_notes = '\n'.join(notes_parts)

                    # Create the message
                    message = CampaignMessage.objects.create(
                        campaign=campaign,
                        message_type='promotion',
                        name=f"Promo: {promo_title[:40]}..." if len(promo_title) > 40 else f"Promo: {promo_title}",
                        custom_subject=promo_title,
                        custom_content=promo_details,
                        notes=combined_notes,
                        order=next_order,
                        status='draft',
                        trigger_type='specific_date' if scheduled_date else 'immediate',
                        scheduled_date=scheduled_date
                    )

                    # Create discount for all promotions
                    try:
                        # For BOGO, use 50 as the value (50% off second item is standard)
                        # For Free Shipping, use 0 (just a flag, actual shipping cost calculated at checkout)
                        if discount_type == 'bogo':
                            discount_value = '50'
                        elif discount_type == 'free_shipping':
                            discount_value = '0'

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
                                applies_to_all=False if product_ids else True
                            )
                            # Link products to discount if specified
                            if product_ids:
                                products_for_discount = Product.objects.filter(id__in=product_ids)
                                discount.products.set(products_for_discount)

                            message.discount = discount
                            message.save()
                    except Exception as e:
                        messages.error(request, f'Error creating discount: {str(e)}')
                        return redirect('admin_campaigns_list')

                    # Link products to message if selected
                    if product_ids:
                        products = Product.objects.filter(id__in=product_ids)
                        message.products.set(products)

                    success_msg = f"{'Public sale' if promo_type == 'public' else 'Private promotion'} added to campaign!"
                    if promo_code:
                        success_msg += f" Code: {promo_code}"
                    messages.success(request, success_msg)

                elif message_type == 'product':
                    from shop.models import Product, ProductVariant

                    product_variant = request.POST.get('product_variant', '').strip()
                    announcement_title = request.POST.get('product_announcement_title', '').strip()
                    announcement_details = request.POST.get('product_announcement_details', '').strip()
                    media_url = request.POST.get('product_media_url', '').strip()
                    release_time = request.POST.get('product_release_time', '09:00').strip()

                    if not product_variant:
                        messages.error(request, 'Product or variant selection is required!')
                        return redirect('admin_campaigns_list')

                    # Parse product_variant (format: "product_123" or "variant_456")
                    product_name = ""
                    selected_products = []
                    if product_variant.startswith('product_'):
                        product_id = product_variant.replace('product_', '')
                        try:
                            product = Product.objects.get(id=product_id)
                            product_name = f"{product.name} (All Variants)"
                            selected_products = [product]
                        except Product.DoesNotExist:
                            messages.error(request, 'Selected product not found!')
                            return redirect('admin_campaigns_list')
                    elif product_variant.startswith('variant_'):
                        variant_id = product_variant.replace('variant_', '')
                        try:
                            variant = ProductVariant.objects.get(id=variant_id)
                            product_name = f"{variant.product.name} - {variant.name}"
                            selected_products = [variant.product]
                        except ProductVariant.DoesNotExist:
                            messages.error(request, 'Selected variant not found!')
                            return redirect('admin_campaigns_list')

                    # Build message name and notes
                    name = announcement_title if announcement_title else f"Product Release: {product_name}"
                    notes = f"Product: {product_name}\nRelease Time: {release_time}"
                    if announcement_details:
                        notes += f"\nDetails: {announcement_details}"

                    # Combine scheduled date with release time if provided
                    product_scheduled_date = scheduled_date
                    if scheduled_date and release_time:
                        try:
                            time_parts = release_time.split(':')
                            product_scheduled_date = scheduled_date.replace(
                                hour=int(time_parts[0]),
                                minute=int(time_parts[1]) if len(time_parts) > 1 else 0
                            )
                        except (ValueError, IndexError):
                            pass

                    message = CampaignMessage.objects.create(
                        campaign=campaign,
                        message_type='product',
                        name=name,
                        custom_subject=announcement_title,
                        custom_content=announcement_details,
                        media_urls=media_url,
                        notes=notes,
                        order=next_order,
                        status='draft',
                        trigger_type='specific_date' if product_scheduled_date else 'immediate',
                        scheduled_date=product_scheduled_date
                    )

                    # Link products to message
                    if selected_products:
                        message.products.set(selected_products)

                    messages.success(request, f'Product release "{name}" added to campaign!')

                return redirect('admin_campaigns_list')
            except Campaign.DoesNotExist:
                messages.error(request, 'Campaign not found!')
                return redirect('admin_campaigns_list')
            except Exception as e:
                messages.error(request, f'Error adding message: {str(e)}')
                return redirect('admin_campaigns_list')

        elif action == 'update_message_date':
            try:
                from django.http import JsonResponse
                message_id = request.POST.get('message_id')
                scheduled_date_str = request.POST.get('scheduled_date')

                message = CampaignMessage.objects.get(id=message_id)

                # Parse scheduled date
                if scheduled_date_str:
                    try:
                        # Parse date string (format: YYYY-MM-DD)
                        scheduled_date = timezone.datetime.strptime(scheduled_date_str, '%Y-%m-%d')
                        scheduled_date = timezone.make_aware(scheduled_date)
                        message.scheduled_date = scheduled_date
                        message.trigger_type = 'specific_date'
                        message.save()

                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({'success': True})
                        else:
                            messages.success(request, 'Message date updated successfully!')
                            return redirect('admin_campaigns_list')
                    except ValueError as e:
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({'success': False, 'error': f'Invalid date format: {str(e)}'})
                        else:
                            messages.error(request, f'Invalid date format: {str(e)}')
                            return redirect('admin_campaigns_list')
                else:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({'success': False, 'error': 'No date provided'})
                    else:
                        messages.error(request, 'No date provided')
                        return redirect('admin_campaigns_list')
            except CampaignMessage.DoesNotExist:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'Message not found'})
                else:
                    messages.error(request, 'Message not found!')
                    return redirect('admin_campaigns_list')
            except Exception as e:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': str(e)})
                else:
                    messages.error(request, f'Error updating message date: {str(e)}')
                    return redirect('admin_campaigns_list')

        elif action == 'edit_message':
            try:
                from django.http import JsonResponse
                message_id = request.POST.get('message_id')
                message = CampaignMessage.objects.get(id=message_id)
                message_type = message.message_type

                # Update based on message type
                if message_type == 'email':
                    message.custom_subject = request.POST.get('email_subject', '').strip()
                    message.custom_content = request.POST.get('email_body', '').strip()
                    message.send_mode = request.POST.get('email_send_mode', 'auto')
                    message.status = 'draft' if message.send_mode == 'draft' else message.status
                elif message_type == 'sms':
                    message.custom_content = request.POST.get('sms_message', '').strip()
                    message.send_mode = request.POST.get('sms_send_mode', 'auto')
                    message.status = 'draft' if message.send_mode == 'draft' else message.status
                elif message_type == 'instagram':
                    message.custom_subject = request.POST.get('instagram_caption', '').strip()
                    message.media_urls = request.POST.get('instagram_media', '').strip()
                    message.notes = request.POST.get('instagram_notes', '').strip()
                    message.custom_content = message.notes
                elif message_type == 'tiktok':
                    message.custom_subject = request.POST.get('tiktok_caption', '').strip()
                    message.media_urls = request.POST.get('tiktok_media', '').strip()
                    message.notes = request.POST.get('tiktok_notes', '').strip()
                    message.custom_content = message.notes
                elif message_type == 'snapchat':
                    message.custom_subject = request.POST.get('snapchat_caption', '').strip()
                    message.media_urls = request.POST.get('snapchat_media', '').strip()
                    message.notes = request.POST.get('snapchat_notes', '').strip()
                    message.custom_content = message.notes
                elif message_type == 'youtube':
                    message.custom_subject = request.POST.get('youtube_title', '').strip()
                    message.media_urls = request.POST.get('youtube_url', '').strip()
                    message.notes = request.POST.get('youtube_description', '').strip()
                    message.custom_content = message.notes
                elif message_type == 'promotion':
                    from shop.models import Discount, Product

                    promo_title = request.POST.get('promotion_title', '').strip()
                    promo_type = request.POST.get('promotion_type', 'public').strip()
                    promo_code = request.POST.get('promotion_code', '').strip()
                    promo_details = request.POST.get('promotion_details', '').strip()

                    message.custom_subject = promo_title
                    message.custom_content = promo_details

                    # Build notes with promotion type and code info
                    notes_parts = []
                    if promo_type == 'public':
                        notes_parts.append('Type: Public Sale (No code required)')
                    else:
                        notes_parts.append('Type: Private/Code Only')
                        if promo_code:
                            notes_parts.append(f'Code: {promo_code}')

                    if promo_details:
                        notes_parts.append(f'\nDetails: {promo_details}')

                    message.notes = '\n'.join(notes_parts)

                    # Update discount if changed
                    discount_id = request.POST.get('promotion_discount', '').strip()
                    if discount_id:
                        try:
                            discount = Discount.objects.get(id=discount_id)
                            message.discount = discount
                        except Discount.DoesNotExist:
                            message.discount = None
                    else:
                        message.discount = None

                    # Update products if changed
                    product_ids = request.POST.getlist('promotion_products')
                    if product_ids:
                        products = Product.objects.filter(id__in=product_ids)
                        message.products.set(products)
                    else:
                        message.products.clear()

                message.save()

                messages.success(request, 'Message updated successfully!')
                return redirect('admin_campaigns_list')
            except CampaignMessage.DoesNotExist:
                messages.error(request, 'Message not found!')
                return redirect('admin_campaigns_list')
            except Exception as e:
                messages.error(request, f'Error updating message: {str(e)}')
                return redirect('admin_campaigns_list')

        elif action == 'delete_message':
            try:
                from django.http import JsonResponse
                message_id = request.POST.get('message_id')
                message = CampaignMessage.objects.get(id=message_id)
                message.delete()

                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True})
                else:
                    messages.success(request, 'Message deleted successfully!')
                    return redirect('admin_campaigns_list')
            except CampaignMessage.DoesNotExist:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'Message not found'})
                else:
                    messages.error(request, 'Message not found!')
                    return redirect('admin_campaigns_list')
            except Exception as e:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': str(e)})
                else:
                    messages.error(request, f'Error deleting message: {str(e)}')
                    return redirect('admin_campaigns_list')

        elif action == 'change_message_status':
            try:
                from django.http import JsonResponse
                message_id = request.POST.get('message_id')
                new_status = request.POST.get('status')

                message = CampaignMessage.objects.get(id=message_id)
                message.status = new_status

                # Update sent_at if status is changed to 'sent'
                if new_status == 'sent' and not message.sent_at:
                    message.sent_at = timezone.now()

                message.save()

                return JsonResponse({'success': True})
            except CampaignMessage.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Message not found'})
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})

        elif action == 'change_campaign_status':
            try:
                from django.http import JsonResponse
                campaign_id = request.POST.get('campaign_id')
                new_status = request.POST.get('status')

                campaign = Campaign.objects.get(id=campaign_id)
                campaign.status = new_status

                # Update started_at if status is changed to 'active' and not set
                if new_status == 'active' and not campaign.started_at:
                    campaign.started_at = timezone.now()

                # Update completed_at if status is changed to 'completed'
                if new_status == 'completed' and not campaign.completed_at:
                    campaign.completed_at = timezone.now()

                campaign.save()

                return JsonResponse({'success': True})
            except Campaign.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Campaign not found'})
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})

    from django.db.models import Count, Q

    campaigns_queryset = Campaign.objects.all().prefetch_related('messages').order_by('-created_at')
    now = timezone.now()

    # Build enriched campaign data
    campaigns = []
    for campaign in campaigns_queryset:
        # Get message counts
        total_messages = campaign.messages.count()
        sent_messages = campaign.messages.filter(status='sent').count()

        # Get message sequence ordered by order field
        message_sequence = list(campaign.messages.all().order_by('order').values('id', 'message_type', 'status', 'name', 'scheduled_date', 'sent_at'))

        # Count messages by type
        email_count = sum(1 for m in message_sequence if m['message_type'] == 'email')
        sms_count = sum(1 for m in message_sequence if m['message_type'] == 'sms')
        instagram_count = sum(1 for m in message_sequence if m['message_type'] == 'instagram')
        tiktok_count = sum(1 for m in message_sequence if m['message_type'] == 'tiktok')
        snapchat_count = sum(1 for m in message_sequence if m['message_type'] == 'snapchat')

        # Calculate progress percentage
        if total_messages > 0:
            progress_percentage = int((sent_messages / total_messages) * 100)
        else:
            progress_percentage = 0

        # Determine display status
        if campaign.active_from and campaign.active_until:
            if now < campaign.active_from:
                display_status = 'upcoming'
            elif now > campaign.active_until:
                display_status = 'completed'
            else:
                display_status = 'active'
        elif campaign.active_from:
            if now >= campaign.active_from:
                display_status = 'active'
            else:
                display_status = 'upcoming'
        elif campaign.active_until:
            if now <= campaign.active_until:
                display_status = 'active'
            else:
                display_status = 'completed'
        else:
            display_status = 'draft'

        # Create enriched campaign object
        campaign_data = {
            'id': campaign.id,
            'name': campaign.name,
            'description': campaign.description,
            'target_group': campaign.target_group,
            'active_from': campaign.active_from,
            'active_until': campaign.active_until,
            'created_at': campaign.created_at,
            'total_messages': total_messages,
            'sent_messages': sent_messages,
            'progress_percentage': progress_percentage,
            'display_status': display_status,
            'message_sequence': message_sequence,
            'email_count': email_count,
            'sms_count': sms_count,
            'instagram_count': instagram_count,
            'tiktok_count': tiktok_count,
            'snapchat_count': snapchat_count,
        }
        campaigns.append(campaign_data)

    # Calculate overview stats
    total_campaigns = len(campaigns)
    active_campaigns = sum(1 for c in campaigns if c['display_status'] == 'active')
    upcoming_campaigns = sum(1 for c in campaigns if c['display_status'] == 'upcoming')
    total_messages = sum(c['total_messages'] for c in campaigns)
    sent_messages = sum(c['sent_messages'] for c in campaigns)

    # Get timeline campaigns (upcoming and active, sorted by start date)
    timeline_campaigns = [c for c in campaigns if c['display_status'] in ['upcoming', 'active']]
    timeline_campaigns.sort(key=lambda c: c['active_from'] if c['active_from'] else timezone.now())

    # Get upcoming messages (not sent yet, across all campaigns)
    upcoming_messages = CampaignMessage.objects.select_related('campaign').exclude(status='sent').order_by('scheduled_date', 'created_at')[:20]
    upcoming_messages_data = []
    for msg in upcoming_messages:
        upcoming_messages_data.append({
            'id': msg.id,
            'name': msg.name,
            'message_type': msg.message_type,
            'campaign_name': msg.campaign.name,
            'campaign_id': msg.campaign.id,
            'status': msg.status,
            'scheduled_date': msg.scheduled_date,
            'created_at': msg.created_at,
            'custom_subject': msg.custom_subject,
        })

    # Get recent messages across all campaigns (most recent 20 sent messages)
    recent_messages = CampaignMessage.objects.select_related('campaign').filter(status='sent').order_by('-sent_at')[:20]
    recent_messages_data = []
    for msg in recent_messages:
        recent_messages_data.append({
            'id': msg.id,
            'name': msg.name,
            'message_type': msg.message_type,
            'campaign_name': msg.campaign.name,
            'campaign_id': msg.campaign.id,
            'status': msg.status,
            'scheduled_date': msg.scheduled_date,
            'sent_at': msg.sent_at,
            'created_at': msg.created_at,
            'custom_subject': msg.custom_subject,
        })

    # Get products for promotion message form
    from shop.models import Product
    products = Product.objects.filter(is_active=True).order_by('name')

    context = {
        'campaigns': campaigns,
        'timeline_campaigns': timeline_campaigns,
        'upcoming_messages': upcoming_messages_data,
        'recent_messages': recent_messages_data,
        'total_campaigns': total_campaigns,
        'active_campaigns': active_campaigns,
        'upcoming_campaigns': upcoming_campaigns,
        'total_messages': total_messages,
        'sent_messages': sent_messages,
        'products': products,
        'cst_time': timezone.now().astimezone(pytz.timezone('America/Chicago')),
    }

    return render(request, 'admin/campaigns_list.html', context)


@staff_member_required
def shipments_dashboard(request):
    """
    Shipments tracking dashboard for incoming inventory.
    """
    from shop.models import Shipment
    from django.http import JsonResponse
    import json
    from datetime import date

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_shipment':
            try:
                shipment = Shipment.objects.create(
                    tracking_number=request.POST.get('tracking_number'),
                    supplier=request.POST.get('supplier'),
                    status=request.POST.get('status'),
                    expected_date=request.POST.get('expected_date'),
                    item_count=request.POST.get('item_count'),
                    notes=request.POST.get('notes', '')
                )
                return JsonResponse({'success': True, 'shipment_id': shipment.id})
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})

        elif action == 'update_shipment':
            try:
                shipment_id = request.POST.get('shipment_id')
                shipment = Shipment.objects.get(id=shipment_id)

                shipment.tracking_number = request.POST.get('tracking_number')
                shipment.supplier = request.POST.get('supplier')
                shipment.status = request.POST.get('status')
                shipment.expected_date = request.POST.get('expected_date')
                shipment.item_count = request.POST.get('item_count')
                shipment.notes = request.POST.get('notes', '')
                
                # Set actual delivery date if status is delivered
                if shipment.status == 'delivered' and not shipment.actual_delivery_date:
                    shipment.actual_delivery_date = date.today()
                
                shipment.save()
                return JsonResponse({'success': True})
            except Shipment.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Shipment not found'})
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})

    # Get all shipments
    shipments = Shipment.objects.all()

    # Calculate stats
    stats = {
        'pending': shipments.filter(status='pending').count(),
        'in_transit': shipments.filter(status='in-transit').count(),
        'delivered': shipments.filter(status='delivered').count(),
        'delayed': shipments.filter(status='delayed').count(),
    }

    # Prepare data for template and JSON
    shipments_data = []
    for shipment in shipments:
        shipments_data.append({
            'id': shipment.id,
            'tracking_number': shipment.tracking_number,
            'supplier': shipment.supplier,
            'status': shipment.status,
            'expected_date': shipment.expected_date.isoformat(),
            'item_count': shipment.item_count,
            'notes': shipment.notes,
        })

    context = {
        'shipments': shipments_data,
        'shipments_json': json.dumps(shipments_data),
        'stats': stats,
        'cst_time': timezone.now().astimezone(pytz.timezone('America/Chicago')),
    }

    return render(request, 'admin/shipments_dashboard.html', context)


@staff_member_required
def orders_dashboard(request):
    """
    Orders management dashboard.
    """
    from shop.models import Order, OrderItem
    from django.http import JsonResponse
    from django.db.models import Count, Sum
    import json

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_order_status':
            try:
                order_id = request.POST.get('order_id')
                order = Order.objects.get(id=order_id)
                order.status = request.POST.get('status')
                order.save()
                return JsonResponse({'success': True})
            except Order.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Order not found'})
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})

    # Get all orders
    orders = Order.objects.all().select_related('user').prefetch_related('items')

    # Calculate stats using OrderStatus choices
    from shop.models import OrderStatus
    stats = {
        'total': orders.count(),
        'pending': orders.filter(status=OrderStatus.CREATED).count(),
        'processing': orders.filter(status=OrderStatus.AWAITING_PAYMENT).count(),
        'shipped': orders.filter(status=OrderStatus.SHIPPED).count(),
        'delivered': orders.filter(status=OrderStatus.FULFILLED).count(),
        'total_revenue': orders.filter(status=OrderStatus.PAID).aggregate(Sum('total'))['total__sum'] or 0,
    }

    # Prepare orders data
    orders_data = []
    for order in orders[:50]:  # Limit to 50 most recent
        user_name = f"{order.user.first_name} {order.user.last_name}" if order.user else "Guest"
        orders_data.append({
            'id': order.id,
            'order_number': f"#{order.id}",
            'customer_name': user_name,
            'customer_email': order.email or (order.user.email if order.user else ''),
            'status': order.status,
            'total': float(order.total),
            'created_at': order.created_at.isoformat(),
            'item_count': order.items.count(),
        })

    context = {
        'orders': orders_data,
        'orders_json': json.dumps(orders_data),
        'stats': stats,
        'cst_time': timezone.now().astimezone(pytz.timezone('America/Chicago')),
    }

    return render(request, 'admin/orders_dashboard.html', context)


@staff_member_required
def returns_dashboard(request):
    """
    Returns and exchanges management dashboard (placeholder).
    """
    # For now, just show a placeholder since we don't have Return model yet
    context = {
        'returns': [],
        'returns_json': '[]',
        'stats': {
            'total': 0,
            'requested': 0,
            'approved': 0,
            'received': 0,
            'refunded': 0,
            'exchanged': 0,
        },
        'cst_time': timezone.now().astimezone(pytz.timezone('America/Chicago')),
    }

    return render(request, 'admin/returns_dashboard.html', context)
