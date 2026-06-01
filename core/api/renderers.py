"""Envelope renderer for the v1 surface (plan 03 — Response envelope).

Every successful v1 response is wrapped as::

    { "data": <payload>, "meta": { "request_id": "req_…", "generated_at": "…Z" } }

Error responses are shaped by ``core.api.exceptions.custom_exception_handler``
(``{"error": {...}, "meta": {...}}``); the paginator
(``core.api.pagination``) shapes paginated successes. Both already carry the
envelope, so this renderer only *fills in* ``meta.request_id`` /
``meta.generated_at`` for them and wraps the bare-payload case.

This renderer is attached per-view via ``V1ViewMixin`` — it is NOT the global
DRF default, so the existing ``/api/`` event endpoints keep their current
response shape.
"""

from django.utils import timezone
from rest_framework.renderers import JSONRenderer

from core.api.request_id import get_request_id


def iso_now() -> str:
    """ISO-8601 UTC with a trailing ``Z`` (plan 03 — datetimes)."""
    return timezone.now().isoformat().replace("+00:00", "Z")


def _is_enveloped(data) -> bool:
    # An already-built envelope from the exception handler or paginator: it has
    # ``meta`` plus exactly one of ``data`` / ``error``. Requiring ``meta`` keeps
    # a plain view payload that merely contains a "data" key from being mistaken
    # for an envelope.
    return (
        isinstance(data, dict)
        and "meta" in data
        and ("data" in data or "error" in data)
    )


class EnvelopeJSONRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        request = renderer_context.get("request")

        if _is_enveloped(data):
            envelope = data
        else:
            envelope = {"data": data, "meta": {}}

        meta = envelope.setdefault("meta", {})
        meta.setdefault("request_id", get_request_id(request))
        meta.setdefault("generated_at", iso_now())

        return super().render(envelope, accepted_media_type, renderer_context)
