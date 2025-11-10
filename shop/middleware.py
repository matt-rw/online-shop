from .models import ConnectionLog


class ConnectionLogMiddleware:
    """
    Middleware to log all requests to the application
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Get IP address
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0]
        else:
            ip_address = request.META.get('REMOTE_ADDR')

        # Get user agent
        user_agent = request.META.get('HTTP_USER_AGENT', '')

        # Get current user (if authenticated)
        user = request.user if request.user.is_authenticated else None

        # Process the request
        response = self.get_response(request)

        # Log the connection (async to avoid slowing down requests)
        try:
            # Only log certain paths to avoid too much data
            if not request.path.startswith('/static/') and not request.path.startswith('/media/'):
                ConnectionLog.objects.create(
                    ip_address=ip_address,
                    user_agent=user_agent[:500],  # Truncate long user agents
                    path=request.path,
                    method=request.method,
                    user=user,
                    status_code=response.status_code,
                )
        except Exception:
            # Silently fail to avoid breaking the app
            pass

        return response
