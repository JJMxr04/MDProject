from django.db import connection
from django.http import HttpResponse, HttpResponseNotFound, JsonResponse
from django.shortcuts import redirect


# Public marketing routes — these are the only paths search engines should
# index. Everything else (the auth-gated portal, admin, API, internal hooks)
# is explicitly disallowed below.
_ALLOWED_PATHS = (
    "/$",
    "/about/",
    "/privacy-policy/",
    "/services/",
    # /game-rules/ moved to auth-gated /web/portal/rules/ — no longer
    # crawlable.
    "/auth/waitlist/",
    "/auth/login/",
    "/auth/signup/",
)

# Routes that must NEVER appear in search results.
_DISALLOWED_PREFIXES = (
    "/web/",          # the entire user portal
    "/admin/",        # Django admin + Jazzmin
    "/api/",          # DRF / API endpoints
    "/auth/",         # user-specific auth endpoints (password reset, etc.)
    "/sportgameodds/",  # inbound webhook receiver
    "/static/",       # don't index static assets directly
    "/media/",        # user-uploaded content
)


def healthz(request):
    """Container health endpoint. Coolify (and any other orchestrator)
    polls this to decide if the instance is ready to take traffic.

    Two checks:
      - process is up (we got here, that's the answer)
      - DB is reachable (a single ``SELECT 1`` — fails fast on bad
        DATABASE_URL or postgres being down)
    """
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
            c.fetchone()
    except Exception as exc:  # noqa: BLE001
        return JsonResponse({"ok": False, "db": str(exc)[:200]}, status=503)
    return JsonResponse({"ok": True})


_PORTAL_404_REDIRECT_PREFIXES = ("/web/portal/", "/admin/")


def portal_or_404(request, exception=None):
    """Custom ``handler404``.

    Anonymous-area URLs (``/web/portal/...``, ``/admin/...``) that don't
    resolve redirect to the public landing instead of showing a 404 —
    matches the AnonymousPortalRedirectMiddleware behaviour for paths
    that *do* exist but aren't accessible. Everything else gets a normal
    404 so missing API routes still surface as 404 to clients.
    """
    path = request.path
    if path.startswith(_PORTAL_404_REDIRECT_PREFIXES):
        return redirect("/")
    return HttpResponseNotFound(
        "<h1>404</h1><p>The page you requested could not be found.</p>",
        content_type="text/html",
    )


def robots_txt(request):
    """Strict robots.txt — block by default, allow only the public marketing
    pages. Same policy is enforced server-side via the
    ``NoIndexPrivateRoutesMiddleware`` ``X-Robots-Tag`` header so a
    misbehaving crawler that ignores robots.txt still won't get its result
    indexed by well-behaved engines downstream."""
    lines = ["User-agent: *"]
    for prefix in _DISALLOWED_PREFIXES:
        lines.append(f"Disallow: {prefix}")
    # Explicitly allow the public landing pages so the disallow rules above
    # don't accidentally over-match (e.g. ``/auth/`` disallow shadowing
    # ``/auth/waitlist/``).
    for path in _ALLOWED_PATHS:
        lines.append(f"Allow: {path.rstrip('$')}")
    lines.append("")
    return HttpResponse("\n".join(lines), content_type="text/plain")
