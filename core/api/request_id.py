"""Per-request correlation id for the v1 envelope.

Every v1 response (success and error) carries ``meta.request_id`` so a user can
quote it to support and we can grep it out of structured logs. The id is minted
once per request and cached on the request object so the renderer and the
exception handler agree on the same value.
"""

import uuid


def _new_id() -> str:
    return f"req_{uuid.uuid4().hex[:24]}"


def get_request_id(request) -> str:
    """Return (minting once) the request id for this request.

    ``request`` is the DRF ``Request`` (or ``None`` in odd renderer contexts).
    We stash the value on the object so repeated calls within one request return
    the same id.
    """
    if request is None:
        return _new_id()
    existing = getattr(request, "_api_request_id", None)
    if existing:
        return existing
    rid = _new_id()
    try:
        request._api_request_id = rid
    except (AttributeError, TypeError):
        pass
    return rid
