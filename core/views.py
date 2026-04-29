from django.http import HttpResponse


# Public marketing routes — these are the only paths search engines should
# index. Everything else (the auth-gated portal, admin, API, internal hooks)
# is explicitly disallowed below.
_ALLOWED_PATHS = (
    "/$",
    "/about/",
    "/privacy-policy/",
    "/services/",
    "/game-rules/",
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
