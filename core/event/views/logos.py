"""Keyless team-logo bytes served from MDProject's own Postgres."""

from __future__ import annotations

from django.http import HttpResponse, HttpResponseNotModified
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

from core.event.models import TeamLogo

LOGO_MAX_AGE = 86400


@require_GET
@cache_control(public=True, max_age=LOGO_MAX_AGE)
def team_logo(request, team_id: str):
    row = TeamLogo.objects.filter(pk=team_id, status="ok").first()
    if row is None or row.image is None:
        return HttpResponse(status=404)

    etag = f'"{row.etag}"'
    if request.META.get("HTTP_IF_NONE_MATCH", "").strip() == etag:
        resp = HttpResponseNotModified()
        resp["ETag"] = etag
        return resp

    resp = HttpResponse(bytes(row.image), content_type=row.content_type or "image/png")
    resp["ETag"] = etag
    return resp
