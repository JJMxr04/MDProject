from django.shortcuts import redirect, render
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers

# 15-minute server-side cache for anonymous marketing pages. These
# templates are 100% static-ish (no per-request data, no auth state),
# so the rendered HTML is identical for every visitor. Caching at the
# view layer skips template render + every DB/Redis call for warm hits.
#
# vary_on_headers("Cookie") keeps logged-in vs anonymous responses
# separate so we never serve a stale "Login" navbar to a signed-in user.
# Whitenoise still handles static assets independently.
MARKETING_CACHE_SECONDS = 60 * 15


def _cached_view(view):
    return cache_page(MARKETING_CACHE_SECONDS)(vary_on_headers("Cookie")(view))


@_cached_view
def home(request):
    return render(request, 'public/home.html')


@_cached_view
def about(request):
    return render(request, 'public/aboutUs.html')


@_cached_view
def privacy_policy(request):
    return render(request, 'public/privacyPolicy.html')


@_cached_view
def terms(request):
    return render(request, 'public/terms.html')


@_cached_view
def contact(request):
    return render(request, 'public/contact.html')


def gameRules(request):
    """Old public URL — rules now live in the auth-gated portal so only
    real users see them. ``login_required`` on ``portal-rules`` will bounce
    anonymous traffic to the login page; signed-in users land directly."""
    return redirect('core-portal:portal-rules')
