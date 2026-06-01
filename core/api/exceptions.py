"""Single error handler for the v1 surface (plan 03 — Errors).

Wraps every DRF exception into the error envelope, attaches ``request_id``, and
**strips internal detail from 5xx** (info-leakage control — a bug never leaks a
traceback or an ORM message to the client; the ``request_id`` is the only handle
support needs).

Scoped to v1 via ``V1ViewMixin.get_exception_handler`` — it is NOT the global
DRF ``EXCEPTION_HANDLER``, so the existing ``/api/`` event endpoints keep their
current ``{"detail": …}`` error shape until they migrate.

404-not-403 policy: object-level permission failures should surface as 404 (don't
leak existence). That is enforced at the queryset layer (``OwnedQuerysetMixin`` +
fetching objects from the scoped queryset) — by the time a real ``PermissionDenied``
reaches here it is an *intentional* 403 (e.g. paywall), so we honor the status DRF
chose rather than rewriting 403→404 blindly.
"""

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from core.api.request_id import get_request_id

# HTTP status -> stable machine code (plan 03 table).
CODE_BY_STATUS = {
    400: "validation_error",
    401: "not_authenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    406: "not_acceptable",
    409: "conflict",
    415: "unsupported_media_type",
    429: "rate_limited",
    502: "upstream_unavailable",
}

_GENERIC_5XX_MESSAGE = "An unexpected error occurred. Quote the request_id to support."


def _message_and_details(detail, status_code):
    """Derive a human ``message`` + structured ``details`` from DRF's ``exc.detail``."""
    # Single-key {"detail": "..."} is DRF's shape for most non-validation errors.
    if isinstance(detail, dict) and set(detail.keys()) == {"detail"}:
        return str(detail["detail"]), {}
    if status_code == 400:
        # Validation: mirror DRF's {field: [msgs]} into details.
        if isinstance(detail, dict):
            return "Validation failed.", detail
        if isinstance(detail, list):
            return "Validation failed.", {"non_field_errors": detail}
        return "Validation failed.", {}
    if isinstance(detail, dict):
        return "Request could not be processed.", detail
    if isinstance(detail, list):
        return "Request could not be processed.", {"non_field_errors": detail}
    return str(detail), {}


def custom_exception_handler(exc, context):
    request = context.get("request") if context else None
    response = drf_exception_handler(exc, context)

    if response is None:
        # Unhandled exception -> 500. DRF would otherwise let Django render it
        # (HTML / traceback). We return a clean, detail-free JSON envelope.
        return Response(
            {
                "error": {
                    "code": "server_error",
                    "message": _GENERIC_5XX_MESSAGE,
                    "details": {},
                },
                "meta": {"request_id": get_request_id(request)},
            },
            status=500,
        )

    status_code = response.status_code
    code = CODE_BY_STATUS.get(
        status_code, "server_error" if status_code >= 500 else "error"
    )

    if status_code >= 500:
        message, details = _GENERIC_5XX_MESSAGE, {}
    else:
        message, details = _message_and_details(response.data, status_code)

    response.data = {
        "error": {"code": code, "message": message, "details": details},
        "meta": {"request_id": get_request_id(request)},
    }
    # DRF already set Retry-After on the response for Throttled — preserved
    # because we mutate the existing response in place.
    return response
