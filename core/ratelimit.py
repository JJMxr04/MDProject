"""Cache-backed rate limiting for plain Django (non-DRF) views.

The DRF surface gets throttling via ``core.api.throttling`` + ``V1ViewMixin``;
the portal's function/class views (auth forms, invite creation) sit outside
DRF and previously had none — an anonymous caller could submit the waitlist
form (one outbound email per POST) or blast match/friend invites without
limit (plan §7.5 item 3).

Counters live in the Django default cache (DatabaseCache) so the limits are
shared across gunicorn workers and replicas, same as the DRF throttles.
Fixed window: the TTL starts at the first hit and is not extended by later
hits. Advisory, not exact — concurrent first-hits can slightly overshoot,
which is fine for a brake.
"""

from functools import wraps

from django.core.cache import cache
from django.http import HttpResponse, JsonResponse

from core.ip import get_client_ip


def _too_many(request, window_seconds):
    wants_json = (
        request.content_type == "application/json"
        or "application/json" in (request.headers.get("Accept") or "")
    )
    if wants_json:
        resp = JsonResponse({"error": "Too many requests. Try again later."}, status=429)
    else:
        resp = HttpResponse(
            "Too many requests. Try again later.", status=429, content_type="text/plain"
        )
    resp["Retry-After"] = str(window_seconds)
    return resp


def rate_limit(scope, limit, window_seconds, per="ip"):
    """Cap a view at ``limit`` requests per ``window_seconds``.

    ``per="ip"`` keys on the real client IP (Cloudflare-aware, see core.ip) —
    use for anonymous endpoints. ``per="user"`` keys on the authenticated
    user id and falls back to IP for anonymous callers.
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if per == "user" and request.user.is_authenticated:
                ident = f"u:{request.user.pk}"
            else:
                ident = f"ip:{get_client_ip(request) or 'unknown'}"
            cache_key = f"ratelimit:{scope}:{ident}"

            if cache.add(cache_key, 1, timeout=window_seconds):
                count = 1
            else:
                try:
                    count = cache.incr(cache_key)
                except ValueError:
                    # Key expired between add() and incr() — new window.
                    cache.add(cache_key, 1, timeout=window_seconds)
                    count = 1

            if count > limit:
                return _too_many(request, window_seconds)
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
