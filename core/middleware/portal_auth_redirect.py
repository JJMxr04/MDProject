"""Redirect anonymous visitors away from gated areas back to the
public landing page, instead of bouncing them through ``/auth/login/``.

Why this exists:
- The portal (``/web/portal/...``) and Django admin (``/admin/...``) are
  the only authenticated surfaces on the site. A logged-out user landing
  on any of those paths should be treated like they hit the marketing
  site root — they haven't started an auth flow, and we don't want to
  advertise the existence of internal URLs to drive-by traffic.
- Per-view ``login_required(login_url="/auth/login/")`` would otherwise
  send them to a login form. That's the right behavior INSIDE an
  established session flow, but not for a cold visitor.
- Combined with the custom ``handler404`` in ``CoreRoot/urls.py``, any
  unknown ``/web/portal/...`` or ``/admin/...`` URL also redirects to
  ``/`` instead of showing a Django 404 page.

This middleware is intentionally narrow: it does NOT intercept
``/admin/login/`` itself (admin needs its own login form to be
reachable), and it does NOT intercept API or webhook paths.
"""

from __future__ import annotations

from django.shortcuts import redirect

# Paths that, when accessed anonymously, redirect to ``/``.
# Order matters — match longest-first. ``/admin/login/`` is explicitly
# allowed through so the admin login form remains reachable.
_PROTECTED_PREFIXES: tuple[str, ...] = (
    "/web/portal/",
    "/admin/",
)
_PROTECTED_BYPASS: tuple[str, ...] = (
    "/admin/login/",
    "/admin/logout/",
    "/admin/password_reset/",
    "/admin/password_reset/done/",
    "/admin/reset/",  # the reset confirmation URLs all start here
)


class AnonymousPortalRedirectMiddleware:
    """Redirect anonymous requests to gated areas back to the public root."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._should_redirect(request):
            return redirect("/")
        return self.get_response(request)

    @staticmethod
    def _should_redirect(request) -> bool:
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            return False
        path = request.path
        if not path.startswith(_PROTECTED_PREFIXES):
            return False
        if any(path.startswith(p) for p in _PROTECTED_BYPASS):
            return False
        return True
