"""Middleware that sets ``X-Robots-Tag: noindex, nofollow`` on every
non-public route.

robots.txt is the polite signal — well-behaved crawlers will skip the URL
entirely. ``X-Robots-Tag`` is the binding one — a crawler that ignored
robots.txt and fetched the page anyway still gets told "don't index this"
in the response, which Google et al. honor at result-rendering time.

The list of public prefixes mirrors ``core.views._ALLOWED_PATHS`` so the
two stay in sync.
"""

from __future__ import annotations

# Anything starting with one of these is fair game for indexing.
_PUBLIC_PREFIXES = (
    "/about/",
    "/privacy-policy/",
    "/services/",
    # /game-rules/ moved to /web/portal/rules/ (auth-gated).
    "/auth/waitlist/",
    "/auth/login/",
    "/auth/signup/",
    "/robots.txt",
    "/favicon.ico",
    "/healthz",   # container health probe — never indexed but no noise either
)


def _is_public(path: str) -> bool:
    if path == "/":
        return True
    return any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES)


class NoIndexPrivateRoutesMiddleware:
    """Stamp ``X-Robots-Tag`` on every response that isn't on a public page.

    Cheap — the check is a string-prefix scan over a small tuple. Runs after
    the view executes so it never blocks rendering."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not _is_public(request.path):
            # Multiple values comma-joined per the X-Robots-Tag spec.
            response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        return response
