import logging
import threading
import time
from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

import requests

from shop.models import PageView, VisitorSession

logger = logging.getLogger(__name__)

# Cache GeoIP lookups for 24 hours
GEOIP_CACHE_TIMEOUT = 86400


class VisitorTrackingMiddleware:
    """
    Middleware to track page views and visitor sessions.
    All tracking runs in a background thread to avoid blocking the response.
    GeoIP lookups are cached per IP for 24 hours.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Start timing
        start_time = time.time()

        # Process the request
        response = self.get_response(request)

        # Calculate response time
        response_time_ms = int((time.time() - start_time) * 1000)

        # Skip tracking for admin, static files, and media
        path = request.path
        if self._should_skip_tracking(path):
            return response

        # Collect request data before the request object goes out of scope
        tracking_data = {
            "path": request.path,
            "method": request.method,
            "ip_address": self._get_client_ip(request),
            "user_agent": request.META.get("HTTP_USER_AGENT", ""),
            "referrer": request.META.get("HTTP_REFERER", ""),
            "session_key": request.session.session_key,
            "response_time_ms": response_time_ms,
        }

        # Ensure session exists
        if not tracking_data["session_key"]:
            request.session.create()
            tracking_data["session_key"] = request.session.session_key

        # Run tracking in background thread so it doesn't block the response
        thread = threading.Thread(
            target=self._track_in_background,
            args=(tracking_data,),
            daemon=True,
        )
        thread.start()

        return response

    def _should_skip_tracking(self, path):
        """Determine if this path should be skipped."""
        skip_prefixes = [
            "/bp-manage/",
            "/bp-djadmin/",
            "/static/",
            "/media/",
            "/__reload__/",
            "/accounts/",
        ]
        return any(path.startswith(prefix) for prefix in skip_prefixes)

    def _track_in_background(self, data):
        """Run all tracking work in a background thread."""
        try:
            ip_address = data["ip_address"]
            user_agent = data["user_agent"]
            referrer = data["referrer"]

            # Parse referrer domain
            referrer_domain = ""
            if referrer:
                try:
                    referrer_domain = urlparse(referrer).netloc
                except Exception:
                    pass

            # Detect device type and browser
            device_type = self._detect_device_type(user_agent, data["path"])
            browser = self._detect_browser(user_agent)
            os = self._detect_os(user_agent)

            # Get location data (cached per IP)
            location_data = self._get_location(ip_address)

            # Create page view record
            PageView.objects.create(
                path=data["path"],
                method=data["method"],
                ip_address=ip_address,
                user_agent=user_agent[:500],
                referrer=referrer[:1000] if referrer else None,
                referrer_domain=referrer_domain,
                device_type=device_type,
                browser=browser,
                os=os,
                response_time_ms=data["response_time_ms"],
                session_id=data["session_key"],
                **location_data,
            )

            # Update or create visitor session
            session, created = VisitorSession.objects.get_or_create(
                session_id=data["session_key"],
                defaults={
                    "landing_page": data["path"],
                    "referrer": referrer[:1000] if referrer else None,
                    "ip_address": ip_address,
                    "user_agent": user_agent[:500],
                    "device_type": device_type,
                    "first_seen": timezone.now(),
                    "last_seen": timezone.now(),
                    "page_views": 1,
                    **{
                        k: v
                        for k, v in location_data.items()
                        if k in ["country", "country_name", "region", "city", "latitude", "longitude"]
                    },
                },
            )

            if not created:
                session.last_seen = timezone.now()
                session.page_views += 1
                session.save(update_fields=["last_seen", "page_views"])

        except Exception as e:
            logger.debug(f"Analytics tracking error: {e}")

    def _get_location(self, ip_address):
        """Get geographic location from IP address. Cached per IP for 24 hours."""
        empty_location = {
            "country": "",
            "country_name": "",
            "region": "",
            "city": "",
            "latitude": None,
            "longitude": None,
        }

        if not ip_address:
            return empty_location

        # Skip private/local IPs
        if (
            ip_address in ["127.0.0.1", "localhost"]
            or ip_address.startswith("192.168.")
            or ip_address.startswith("10.")
            or ip_address.startswith("172.")
        ):
            return empty_location

        # Check cache first
        cache_key = f"geoip_{ip_address}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            response = requests.get(
                f"http://ip-api.com/json/{ip_address}",
                timeout=2,
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    location_data = {
                        "country": data.get("countryCode", ""),
                        "country_name": data.get("country", ""),
                        "region": data.get("regionName", ""),
                        "city": data.get("city", ""),
                        "latitude": data.get("lat"),
                        "longitude": data.get("lon"),
                    }
                    cache.set(cache_key, location_data, GEOIP_CACHE_TIMEOUT)
                    return location_data

        except Exception:
            pass

        # Cache empty result too to avoid retrying failed lookups
        cache.set(cache_key, empty_location, GEOIP_CACHE_TIMEOUT)
        return empty_location

    def _get_client_ip(self, request):
        """Get the client's IP address."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip

    def _detect_device_type(self, user_agent, path=None):
        """Simple device type detection with enhanced bot detection."""
        ua_lower = user_agent.lower()

        bot_indicators = [
            "bot", "crawl", "spider", "scrape", "curl", "wget", "python",
            "java", "perl", "ruby", "go-http", "node-fetch", "axios",
            "httpie", "postman", "insomnia", "scanner", "probe", "masscan",
            "nmap", "zgrab", "nikto", "sqlmap", "wpscan", "nuclei", "httpx"
        ]
        if any(indicator in ua_lower for indicator in bot_indicators):
            return "bot"

        if path:
            suspicious_paths = [
                ".env", ".git", ".svn", ".htaccess", ".htpasswd",
                "wp-login", "wp-admin", "wp-config", "xmlrpc.php",
                "phpmyadmin", "adminer", "phpinfo",
                ".sql", ".bak", ".backup", ".old",
                "admin.php", "login.php", "config.php",
                "/etc/passwd", "/etc/shadow",
                "shell.php", "cmd.php", "eval-stdin",
                ".aws", ".ssh", "credentials",
            ]
            path_lower = path.lower()
            if any(sus in path_lower for sus in suspicious_paths):
                return "bot"

        if len(user_agent.strip()) < 10:
            return "bot"

        mobile_indicators = [
            "mobile", "android", "iphone", "ipad", "ipod",
            "blackberry", "windows phone",
        ]
        if any(indicator in ua_lower for indicator in mobile_indicators):
            if "ipad" in ua_lower or "tablet" in ua_lower:
                return "tablet"
            return "mobile"

        return "desktop"

    def _detect_browser(self, user_agent):
        """Simple browser detection."""
        ua_lower = user_agent.lower()

        if "edg" in ua_lower:
            return "Edge"
        elif "chrome" in ua_lower:
            return "Chrome"
        elif "safari" in ua_lower:
            return "Safari"
        elif "firefox" in ua_lower:
            return "Firefox"
        elif "opera" in ua_lower or "opr" in ua_lower:
            return "Opera"
        elif "msie" in ua_lower or "trident" in ua_lower:
            return "Internet Explorer"

        return "Unknown"

    def _detect_os(self, user_agent):
        """Simple OS detection."""
        ua_lower = user_agent.lower()

        if "windows" in ua_lower:
            return "Windows"
        elif "mac os" in ua_lower or "macos" in ua_lower:
            return "macOS"
        elif "linux" in ua_lower:
            return "Linux"
        elif "android" in ua_lower:
            return "Android"
        elif "iphone" in ua_lower or "ipad" in ua_lower:
            return "iOS"

        return "Unknown"
