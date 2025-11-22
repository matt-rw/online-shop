import time
from urllib.parse import urlparse

from django.conf import settings
from django.utils import timezone

import requests

from shop.models import PageView, VisitorSession


class VisitorTrackingMiddleware:
    """
    Middleware to track page views and visitor sessions.
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

        # Track the page view asynchronously (in production, use Celery or similar)
        try:
            self._track_page_view(request, response_time_ms)
        except Exception as e:
            # Silently fail - don't break the site if tracking fails
            print(f"Analytics tracking error: {e}")

        return response

    def _should_skip_tracking(self, path):
        """Determine if this path should be skipped."""
        skip_prefixes = [
            "/admin/",
            "/django-admin/",
            "/static/",
            "/media/",
            "/__reload__/",
            "/accounts/",  # Skip allauth pages
        ]
        return any(path.startswith(prefix) for prefix in skip_prefixes)

    def _track_page_view(self, request, response_time_ms):
        """Record page view and update session."""
        # Get visitor information
        ip_address = self._get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        referrer = request.META.get("HTTP_REFERER", "")

        # Parse referrer domain
        referrer_domain = ""
        if referrer:
            try:
                referrer_domain = urlparse(referrer).netloc
            except:
                pass

        # Get or create session ID
        session_id = request.session.session_key
        if not session_id:
            # Create a session if one doesn't exist
            request.session.create()
            session_id = request.session.session_key

        # Detect device type and browser
        device_type = self._detect_device_type(user_agent)
        browser = self._detect_browser(user_agent)
        os = self._detect_os(user_agent)

        # Get location data
        location_data = self._get_location(ip_address)

        # Create page view record
        PageView.objects.create(
            path=request.path,
            method=request.method,
            ip_address=ip_address,
            user_agent=user_agent[:500],  # Truncate long user agents
            referrer=referrer[:1000] if referrer else None,
            referrer_domain=referrer_domain,
            device_type=device_type,
            browser=browser,
            os=os,
            response_time_ms=response_time_ms,
            session_id=session_id,
            **location_data,  # Add country, region, city, etc.
        )

        # Update or create visitor session
        session, created = VisitorSession.objects.get_or_create(
            session_id=session_id,
            defaults={
                "landing_page": request.path,
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
            # Update existing session
            session.last_seen = timezone.now()
            session.page_views += 1
            session.save(update_fields=["last_seen", "page_views"])

    def _get_location(self, ip_address):
        """Get geographic location from IP address using ip-api.com (free, no signup)."""
        location_data = {
            "country": "",
            "country_name": "",
            "region": "",
            "city": "",
            "latitude": None,
            "longitude": None,
        }

        if not ip_address:
            return location_data

        try:
            # Skip private/local IPs
            if (
                ip_address in ["127.0.0.1", "localhost"]
                or ip_address.startswith("192.168.")
                or ip_address.startswith("10.")
            ):
                return location_data

            # Use ip-api.com free API (45 requests/minute, no key needed)
            response = requests.get(
                f"http://ip-api.com/json/{ip_address}",
                timeout=2,  # Short timeout to not slow down requests
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    location_data["country"] = data.get("countryCode", "")
                    location_data["country_name"] = data.get("country", "")
                    location_data["region"] = data.get("regionName", "")
                    location_data["city"] = data.get("city", "")
                    location_data["latitude"] = data.get("lat")
                    location_data["longitude"] = data.get("lon")

        except Exception as e:
            # Silently fail for IPs that can't be geolocated or API issues
            pass

        return location_data

    def _get_client_ip(self, request):
        """Get the client's IP address."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip

    def _detect_device_type(self, user_agent):
        """Simple device type detection."""
        ua_lower = user_agent.lower()

        # Check for bots
        bot_indicators = ["bot", "crawl", "spider", "scrape", "curl", "wget"]
        if any(indicator in ua_lower for indicator in bot_indicators):
            return "bot"

        # Check for mobile
        mobile_indicators = [
            "mobile",
            "android",
            "iphone",
            "ipad",
            "ipod",
            "blackberry",
            "windows phone",
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
