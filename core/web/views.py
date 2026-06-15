from django.conf import settings
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


@_cached_view
def pricing(request):
    # Pull the live PRO price from the Plan row (seeded from the PLATFORM_COST
    # env var via `manage.py sync_platform_cost`) rather than hardcoding it.
    from core.billing.models import Plan
    plan = (Plan.objects.filter(code='PRO', is_active=True).first()
            or Plan.objects.filter(code='PRO').first())
    cents = plan.amount_cents if (plan and plan.amount_cents) else \
        getattr(settings, 'PLATFORM_COST_CENTS', 999)
    ctx = {
        'pro_price': f"{cents / 100:.2f}",
        'pro_interval': plan.interval if plan else 'month',
        'pro_trial_days': getattr(plan, 'trial_days', 0) if plan else 0,
    }
    return render(request, 'public/pricing.html', ctx)


def gameRules(request):
    """Old public URL — rules now live in the auth-gated portal so only
    real users see them. ``login_required`` on ``portal-rules`` will bounce
    anonymous traffic to the login page; signed-in users land directly."""
    return redirect('core-portal:portal-rules')
