"""Stores the current request in a context variable so services can audit with IP/user-agent."""
import contextvars

_current_request = contextvars.ContextVar("current_request", default=None)


def get_current_request():
    return _current_request.get()


def get_client_ip(request):
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        # Nginx appends the real client address; the left-most entry is the originating client.
        return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR")


class RequestContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _current_request.set(request)
        try:
            return self.get_response(request)
        finally:
            _current_request.reset(token)
