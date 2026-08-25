"""Authentication classes for the portal /api/v1 surface.

The project-wide DRF default is JWT-only (see settings.REST_FRAMEWORK), which
the existing /api/ event endpoints + user viewsets rely on. We do NOT change
that global default — instead every v1 view inherits ``V1ViewMixin`` (see
base.py), which sets these classes explicitly so the browser portal can
authenticate with its **session cookie**.

Order matters: SessionAuthentication first so cookie-bearing portal requests
take the cheap path; JWT second so a future mobile/3rd-party client can hit the
same endpoints with a bearer token.

SessionAuthentication enforces CSRF on unsafe methods (POST/PUT/PATCH/DELETE),
which is exactly what we want for cookie-authed state changes. The client
sends X-CSRFToken.
"""

from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication

# Re-exported for use in DEFAULT_AUTHENTICATION_CLASSES-style lists.
V1_AUTHENTICATION_CLASSES = (SessionAuthentication, JWTAuthentication)
