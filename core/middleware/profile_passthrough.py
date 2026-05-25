"""Aggrigator-profile passthrough middleware.

When a request comes in carrying the ``X-Profile-Aggrigator: 1`` header
AND ``AGGRIGATOR_PROFILE_PASSTHROUGH=True`` is set on the env, every
outbound call the view makes via ``core.portal.services.aggrigator_client``
gets ``?profile=1`` appended. The aggrigator returns a pyinstrument flame
graph (HTML) instead of JSON. The client captures those HTML bodies into
a contextvar list and returns ``{}`` to the view so the page doesn't
crash on missing data.

After the view returns, this middleware checks the contextvar — if any
flame graphs were captured, it discards the rendered portal HTML and
returns the flame graphs concatenated as the response body.

Workflow:
  1. operator sets AGGRIGATOR_PROFILE_PASSTHROUGH=True in MDProject env
  2. operator sets AGG_PROFILER_ENABLED=True on the aggrigator
  3. operator opens the slow portal page with the X-Profile-Aggrigator
     header (curl, browser devtools "modify-headers" extension, etc.)
  4. browser receives the flame graph(s) instead of the portal page

Why a contextvar (not threadlocal): Django can run async views. A
contextvar is the only cross-style safe handoff.
"""

from __future__ import annotations

import contextvars
from typing import TYPE_CHECKING

from django.conf import settings
from django.http import HttpResponse

if TYPE_CHECKING:
    from django.http import HttpRequest

# Set to a list when the inbound request opts into passthrough. Stays
# None on requests where passthrough is off, so the client can do a
# cheap None-check on the hot path.
_capture: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar(
    "aggrigator_profile_capture", default=None,
)

# Inbound header that triggers the per-request opt-in.
_HEADER = "HTTP_X_PROFILE_AGGRIGATOR"
_TRUTHY = ("1", "true", "yes", "on")


def is_active() -> bool:
    """Called by aggrigator_client._get on every request — keep cheap."""
    return _capture.get() is not None


def add_capture(html: str) -> None:
    """aggrigator_client stuffs flame-graph HTML here."""
    bucket = _capture.get()
    if bucket is not None:
        bucket.append(html)


class ProfilePassthroughMiddleware:
    """Wraps the request lifecycle around the contextvar handoff."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = getattr(settings, "AGGRIGATOR_PROFILE_PASSTHROUGH", False)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not self.enabled or request.META.get(_HEADER, "").strip().lower() not in _TRUTHY:
            return self.get_response(request)

        token = _capture.set([])
        try:
            response = self.get_response(request)
            captured = _capture.get() or []
        finally:
            _capture.reset(token)

        if not captured:
            return response

        # Concatenate captured flame graphs with simple separators.
        # Multiple aggrigator calls per request (e.g. analytics_league
        # fires fixtures + standings) each contribute a flame graph.
        body_parts = []
        for i, html in enumerate(captured, start=1):
            body_parts.append(
                f"<hr><h2 style='font:14px sans-serif;padding:8px;"
                f"background:#222;color:#fff'>Aggrigator call #{i} of "
                f"{len(captured)}</h2>",
            )
            body_parts.append(html)
        return HttpResponse("".join(body_parts), content_type="text/html")
