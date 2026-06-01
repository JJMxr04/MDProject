"""Scoped throttles for the v1 surface (plan 03 — Throttling; fixes S-9 API side).

Rates live in ``settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']`` so they can be
tuned per-environment without a code change:

    anon            60/min   floor; we don't expect anon on v1
    user           600/min   normal authed portal browsing + polling
    live_odds       60/min   per-user 1/s polling cap for odds cells
    auth_sensitive  10/min   per-IP brute-force / credential-stuffing brake

``V1ViewMixin`` applies ``user``/``anon`` to every v1 view. ``LiveOddsRateThrottle``
and ``AuthSensitiveRateThrottle`` are opt-in per-view (odds endpoints; auth views).

NOTE: DRF throttles count against the Django default cache (DatabaseCache here),
so each throttled request does a cache read/write. Acceptable at current volume;
revisit a dedicated cache backend if the v1 polling load grows.
"""

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class LiveOddsRateThrottle(UserRateThrottle):
    """Per-user cap for hot odds polling (~1 req/s)."""

    scope = "live_odds"


class AuthSensitiveRateThrottle(AnonRateThrottle):
    """Per-IP brake for login / register / password-reset / activation.

    Keyed by IP (inherits ``AnonRateThrottle``'s ident) because the caller is
    typically unauthenticated on these endpoints.
    """

    scope = "auth_sensitive"
