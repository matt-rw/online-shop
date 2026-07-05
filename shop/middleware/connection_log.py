import logging
import threading

from shop.models import ConnectionLog

logger = logging.getLogger(__name__)


class ConnectionLogMiddleware:
    """
    Middleware to log all requests to the application.
    Runs in a background thread to avoid blocking responses.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip static/media early
        if request.path.startswith("/static/") or request.path.startswith("/media/"):
            return self.get_response(request)

        # Collect data before processing
        log_data = {
            "ip_address": self._get_client_ip(request),
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:500],
            "path": request.path,
            "method": request.method,
            "user_id": request.user.pk if request.user.is_authenticated else None,
        }

        # Process the request
        response = self.get_response(request)

        log_data["status_code"] = response.status_code

        # Log in background thread
        thread = threading.Thread(
            target=self._log_in_background,
            args=(log_data,),
            daemon=True,
        )
        thread.start()

        return response

    def _log_in_background(self, data):
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = None
            if data["user_id"]:
                try:
                    user = User.objects.get(pk=data["user_id"])
                except User.DoesNotExist:
                    pass

            ConnectionLog.objects.create(
                ip_address=data["ip_address"],
                user_agent=data["user_agent"],
                path=data["path"],
                method=data["method"],
                user=user,
                status_code=data["status_code"],
            )
        except Exception:
            pass

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0]
        return request.META.get("REMOTE_ADDR")
