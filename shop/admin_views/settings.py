"""
Homepage, security, and site settings admin views.
"""

import json
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

import pytz

from shop.models import (
    ConnectionLog,
    SiteSettings,
)
from shop.models.settings import QuickLink

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


