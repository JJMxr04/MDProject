"""Login-required user-avatar bytes served from MDProject's own Postgres.

Keyed by the opaque ``User.public_id`` UUID (never the enumerable integer
pk). Mirrors core.event.views.logos.team_logo but is access-gated: avatars
are personal data, so only authenticated users may fetch them.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseNotModified
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

from core.user.models import User, UserAvatar

AVATAR_MAX_AGE = 86400


@login_required
@require_GET
@cache_control(private=True, max_age=AVATAR_MAX_AGE)
def user_avatar(request, public_id: str):
    user = User.objects.filter(public_id=public_id).first()
    if user is None:
        return HttpResponse(status=404)

    row = (
        UserAvatar.objects.filter(pk=user.pk, status="ok")
        .only("image", "content_type", "etag")
        .first()
    )
    if row is None or row.image is None:
        return HttpResponse(status=404)

    etag = f'"{row.etag}"'
    if request.META.get("HTTP_IF_NONE_MATCH", "").strip() == etag:
        resp = HttpResponseNotModified()
        resp["ETag"] = etag
        return resp

    resp = HttpResponse(bytes(row.image), content_type=row.content_type or "image/webp")
    resp["ETag"] = etag
    return resp
