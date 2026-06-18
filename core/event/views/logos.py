"""Team-logo bytes for the portal's <img> tags.

Served local-first from MDProject's own Postgres (``TeamLogo``); on a miss we
proxy the crest from the aggregator with the service key applied server-side.
Browsers can't attach the key to an ``<img>`` request, so routing logos through
this same-origin endpoint lets the aggregator's own logo route stay key-gated
while still rendering teams MDProject hasn't mirrored (e.g. aggregator events
not yet selected here). We never persist the proxied bytes: ``TeamLogo``
requires a ``Team`` row, which we deliberately don't create for those teams.
"""

from __future__ import annotations

from django.http import HttpResponse, HttpResponseNotModified
from django.views.decorators.http import require_GET

from core.event.models import TeamLogo
from core.event.providers.aggregator_client import (
    AggrigatorClient,
    AggrigatorError,
    AggrigatorRateLimited,
)

LOGO_MAX_AGE = 86400
# A missing logo is cached briefly so a logo-less team doesn't re-hit the
# aggregator on every page view, while still recovering once a crest appears.
MISSING_MAX_AGE = 300


@require_GET
def team_logo(request, team_id: str):
    row = TeamLogo.objects.filter(pk=team_id, status="ok").first()
    if row is not None and row.image is not None:
        return _serve(
            request,
            content=bytes(row.image),
            content_type=row.content_type,
            etag=f'"{row.etag}"',
        )
    return _proxy_from_aggregator(request, team_id)


def _proxy_from_aggregator(request, team_id: str):
    try:
        result = AggrigatorClient().get_team_logo_bytes(team_id)
    except AggrigatorRateLimited as exc:
        resp = HttpResponse(status=503)
        resp["Retry-After"] = str(exc.retry_after)
        resp["Cache-Control"] = "no-store"
        return resp
    except AggrigatorError:
        resp = HttpResponse(status=503)
        resp["Cache-Control"] = "no-store"
        return resp

    if result is None:
        resp = HttpResponse(status=404)
        resp["Cache-Control"] = f"public, max-age={MISSING_MAX_AGE}"
        return resp

    content, content_type, etag = result
    return _serve(request, content=content, content_type=content_type, etag=etag)


def _serve(request, *, content: bytes, content_type: str | None, etag: str | None):
    """Emit a logo body with shared ETag/304 + cache handling."""
    if etag and request.META.get("HTTP_IF_NONE_MATCH", "").strip() == etag:
        resp = HttpResponseNotModified()
    else:
        resp = HttpResponse(content, content_type=content_type or "image/png")
    if etag:
        resp["ETag"] = etag
    resp["Cache-Control"] = f"public, max-age={LOGO_MAX_AGE}"
    return resp
