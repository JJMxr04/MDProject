"""Activates the authenticated user's timezone + clock format for the request,
so every server-rendered datetime ({{ ... }}, |date, |usertime) comes out in
their chosen zone and clock. Backend is the single source of truth — the client
never localizes times.

Must run AFTER AuthenticationMiddleware (needs request.user). Activation is
defensive and always restored via core.timeprefs.user_time_context (Security
H2/H3).
"""
from core import timeprefs


class TimezonePreferenceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            with timeprefs.user_time_context(user):
                return self.get_response(request)
        return self.get_response(request)
