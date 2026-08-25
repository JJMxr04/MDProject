"""The v1 view spine — every ``/api/v1/`` view inherits ``V1ViewMixin``.

It binds the security defaults in one auditable place:

- **AuthN:** session-cookie first, JWT second (``V1_AUTHENTICATION_CLASSES``).
  SessionAuthentication enforces CSRF on unsafe methods.
- **AuthZ:** ``IsAuthenticated`` deny-by-default; resource views add object-level
  permissions from ``core.api.permissions`` on top.
- **Envelope:** ``EnvelopeJSONRenderer`` (success) + ``custom_exception_handler``
  (errors) — both scoped to v1 here, so the legacy ``/api/`` endpoints are
  untouched.
- **Throttle:** ``user`` / ``anon`` scopes (rates in settings).
- **Pagination:** envelope-aware page-number paginator.

These are set as class attributes (not the global DRF defaults) so this mixin is
the single switch for v1 behavior.
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle

from core.api.auth import V1_AUTHENTICATION_CLASSES
from core.api.exceptions import custom_exception_handler
from core.api.pagination import EnvelopePageNumberPagination
from core.api.renderers import EnvelopeJSONRenderer
from core.api.throttling import ClientIPAnonRateThrottle


class V1ViewMixin:
    authentication_classes = V1_AUTHENTICATION_CLASSES
    permission_classes = [IsAuthenticated]
    renderer_classes = [EnvelopeJSONRenderer]
    throttle_classes = [UserRateThrottle, ClientIPAnonRateThrottle]
    pagination_class = EnvelopePageNumberPagination

    def get_exception_handler(self):
        # Scope the envelope error handler to v1 only (do not set the global
        # DRF EXCEPTION_HANDLER — the legacy /api/ endpoints keep {"detail": …}).
        return custom_exception_handler

    def get_authenticate_header(self, request):
        # Force 401 (not DRF's default 403) for unauthenticated requests.
        # SessionAuthentication is first and returns no authenticate header, so
        # DRF would coerce NotAuthenticated -> 403. Advertise the JWT bearer
        # scheme instead so the status stays 401 — the islands' `pbl:auth-expired`
        # fires on 401, which is how a session expiry surfaces to the user.
        return 'Bearer realm="api"'
