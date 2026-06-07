"""Real-client-IP resolution behind the Cloudflare → Traefik proxy chain.

In production the app sits behind two proxy hops:

    client → Cloudflare edge (orange-cloud) → Coolify Traefik → gunicorn

``REMOTE_ADDR`` is therefore always Traefik's address, and what lands in
``X-Forwarded-For`` depends on whether Traefik trusts its upstream hop
(with Coolify's defaults it does not, in which case XFF holds only the
Cloudflare edge IP — shared by every visitor routed through that PoP).
The one signal that survives both Traefik configurations is
``CF-Connecting-IP``: Cloudflare sets it to the real client IP on every
proxied request, and Traefik only sanitizes ``X-Forwarded-*`` headers —
custom headers pass through untouched.

Resolution order:
  1. ``CF-Connecting-IP``  — authoritative when traffic came through Cloudflare.
  2. ``X-Forwarded-For``   — LAST entry only, i.e. the peer address our own
                             Traefik hop appended. Leftmost entries are
                             client-supplied and spoofable; never use them.
  3. ``REMOTE_ADDR``       — local dev / tests (no proxy in front).

Spoofing note: a client that bypasses Cloudflare and reaches the origin
directly could forge ``CF-Connecting-IP``. The values derived from this
function key rate-limit brakes (axes lockouts, DRF throttles) — not authn —
so the impact is bounded (an attacker can dodge their own bucket, same as
rotating IPs; they cannot weaken anyone else's). To close even that,
firewall the origin to Cloudflare's published IP ranges.
"""


def get_client_ip(request):
    """Best-effort real client IP for axes lockouts and DRF throttle keys."""
    meta = request.META
    cf = (meta.get("HTTP_CF_CONNECTING_IP") or "").strip()
    if cf:
        return cf
    xff = (meta.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if xff:
        return xff.rsplit(",", 1)[-1].strip()
    return meta.get("REMOTE_ADDR")
