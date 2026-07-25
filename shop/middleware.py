import threading

from .models import ConnectionLog


class ConnectionLogMiddleware:
    """
    Middleware to log all requests to the application.
    Logging runs in a background thread to avoid blocking responses.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Get IP address
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(",")[0]
        else:
            ip_address = request.META.get("REMOTE_ADDR")

        # Get user agent
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]

        # Get current user (if authenticated)
        user_id = request.user.pk if request.user.is_authenticated else None

        path = request.path
        method = request.method

        # Process the request
        response = self.get_response(request)

        # Log in background thread to avoid blocking
        if not path.startswith("/static/") and not path.startswith("/media/"):
            status_code = response.status_code
            thread = threading.Thread(
                target=self._log_connection,
                args=(ip_address, user_agent, path, method, user_id, status_code),
                daemon=True,
            )
            thread.start()

        return response

    @staticmethod
    def _log_connection(ip_address, user_agent, path, method, user_id, status_code):
        try:
            from django.contrib.auth.models import User
            ConnectionLog.objects.create(
                ip_address=ip_address,
                user_agent=user_agent,
                path=path,
                method=method,
                user_id=user_id,
                status_code=status_code,
            )
        except Exception:
            pass
