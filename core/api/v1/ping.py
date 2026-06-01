"""``GET/POST /api/v1/_ping/`` — the foundation smoke endpoint (plan 03/10).

Proves the spine end to end before any page migration:
- session auth + ``IsAuthenticated`` (anon -> 401 ``not_authenticated``),
- the success envelope (``data`` + ``meta.request_id`` + ``meta.generated_at``),
- CSRF enforcement on the unsafe ``POST`` for cookie-authed callers.

It is intentionally trivial and exposes no user data beyond the caller's own
identity.
"""

from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.base import V1ViewMixin


class PingView(V1ViewMixin, APIView):
    def get(self, request):
        return Response(
            {
                "pong": True,
                "user": request.user.get_username(),
                "method": "GET",
            }
        )

    def post(self, request):
        # Exists to prove SessionAuthentication's CSRF gate on unsafe methods:
        # a cookie-authed POST without a valid X-CSRFToken is rejected (403).
        return Response({"pong": True, "method": "POST"})
