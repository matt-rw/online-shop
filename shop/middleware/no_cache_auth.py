class NoCacheAuthMiddleware:
    """
    Middleware to prevent caching on authentication pages.
    This prevents CSRF token mismatch errors from stale cached pages.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Add no-cache headers to auth pages
        if request.path.startswith("/accounts/"):
            response["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"

        return response
