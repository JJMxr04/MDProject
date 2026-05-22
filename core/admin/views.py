from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from django.http import Http404

from core.admin.status import (
    check_aggregator,
    check_db,
    check_redis,
    get_beat_schedule,
    get_recent_results,
    get_worker_status,
)

# name → (probe func, human title, partial template, context key)
CHECK_REGISTRY = {
    "postgres":   (check_db,           "Postgres",
                   "admin/status/_check_card.html", "item"),
    "redis":      (check_redis,        "Redis (cache + broker)",
                   "admin/status/_check_card.html", "item"),
    "aggregator": (check_aggregator,   "Aggregator",
                   "admin/status/_check_card.html", "item"),
    "worker":     (get_worker_status,  "Worker",
                   "admin/status/_worker_banner.html", "worker"),
}
from core.billing.services import stripe_setup


@staff_member_required
def custom_admin_view(request):
    context = dict(
        admin.site.each_context(request),
        title='Custom Dashboard',
    )
    return TemplateResponse(request, "admin/dashboard/dashboard.html", context)


@staff_member_required
def status_page(request):
    """Full /admin/status/ page — health checks + beat schedule + recent runs.

    Worker status is rendered both inline (so the page shows current
    state on first paint) and as a polling target via
    ``status_worker_partial`` (so the banner refreshes every 10s
    without a full reload).
    """
    health_checks = [
        ("postgres",   "Postgres",                check_db()),
        ("redis",      "Redis (cache + broker)",  check_redis()),
        ("aggregator", "Aggregator",              check_aggregator()),
    ]
    context = dict(
        admin.site.each_context(request),
        title="Project Status",
        worker=get_worker_status(),
        health_checks=health_checks,
        beat_schedule=get_beat_schedule(),
        recent_results=get_recent_results(limit=25),
    )
    return TemplateResponse(request, "admin/status/index.html", context)


@staff_member_required
@require_http_methods(["GET", "POST"])
def stripe_setup_page(request):
    """One-click Stripe setup page.

    GET: render the current state (key mode, API version, account info)
    plus a form prefilled with the canonical webhook URL for this
    installation, plus a table of webhook events we'd subscribe to and
    capabilities the secret key needs.

    POST: create a fresh ``webhook_endpoint`` in Stripe pointing at the
    submitted URL. Refuses if an endpoint with that URL already exists
    (the user must delete it in the Stripe Dashboard first — auto-delete
    would silently kill a secret in use elsewhere). On success, render
    the same page with the new ``whsec_...`` shown once + a link to
    Stripe Dashboard so the operator can grab it directly there too."""
    default_url = request.build_absolute_uri(
        reverse("billing-stripe-webhook"),
    )

    created = None
    flash = None
    submitted_url = default_url
    existing = None
    # Stripe's API rejects any non-publicly-reachable URL at create
    # time, so we hide the submit button on localhost (or 127.0.0.1)
    # and surface the ``stripe listen`` copy-paste instead.
    is_local = any(
        marker in default_url for marker in
        ("://localhost", "://127.0.0.1", "://0.0.0.0")
    )

    if request.method == "POST":
        submitted_url = (request.POST.get("webhook_url") or default_url).strip()
        try:
            created = stripe_setup.create_webhook_endpoint(submitted_url)
            messages.success(
                request,
                f"Webhook endpoint created: {created.id}. Copy the signing "
                "secret below into STRIPE_WEBHOOK_SECRET and restart the app.",
            )
        except ValueError as exc:
            # Existing-endpoint refusal — surface the URL so the operator
            # can find it in Stripe Dashboard and decide.
            existing = stripe_setup.find_endpoint_by_url(submitted_url)
            flash = str(exc)
            messages.warning(request, flash)
        except Exception as exc:
            flash = f"Stripe error: {exc}"
            messages.error(request, flash)

    state = stripe_setup.status()
    endpoints = []
    connection = None
    if state.key_present and state.error is None:
        try:
            endpoints = stripe_setup.list_endpoints()
        except Exception as exc:
            messages.error(request, f"Could not list webhook endpoints: {exc}")
        # Live re-check of the canonical webhook wiring (endpoint
        # exists + enabled + local secret present). Cheap enough to
        # run on every GET — that's exactly what makes the Refresh
        # button work: it's just a GET round-trip to this view.
        connection = stripe_setup.webhook_connection(default_url)
        if request.GET.get("refresh") == "1" and connection.connected:
            messages.success(request, "Webhook connection looks healthy.")

    context = dict(
        admin.site.each_context(request),
        title="Stripe Setup",
        state=state,
        endpoints=endpoints,
        connection=connection,
        events=stripe_setup.WEBHOOK_EVENTS,
        capabilities=stripe_setup.REQUIRED_CAPABILITIES,
        default_webhook_url=default_url,
        submitted_webhook_url=submitted_url,
        created=created,
        existing_endpoint=existing,
        flash=flash,
        is_local=is_local,
        # Path the Stripe CLI should forward to. We only need the path
        # because the CLI substitutes the localhost host for you.
        stripe_listen_path=reverse("billing-stripe-webhook"),
    )
    return TemplateResponse(request, "admin/stripe_setup.html", context)


@staff_member_required
def status_worker_partial(request):
    """HTML partial with just the worker banner — JS poll target.

    Returned as a fragment (no <html>/<body>) so the polling JS can
    swap it into the banner container directly. Same auth gate as the
    full page.
    """
    context = {"worker": get_worker_status()}
    return TemplateResponse(request, "admin/status/_worker_banner.html", context)


@staff_member_required
def redis_ping_partial(request):
    """HTML partial — fresh Redis probe. Bound to the Dashboard's
    'Ping Now' button. Does not auto-refresh; the button is the only
    trigger.
    """
    from django.utils import timezone
    context = {
        "redis_status": check_redis(),
        "checked_at": timezone.localtime(),
    }
    return TemplateResponse(
        request, "admin/dashboard/_redis_status_bar.html", context,
    )


@staff_member_required
def worker_ping_partial(request):
    """HTML partial — fresh Celery worker ping. Bound to the Dashboard's
    worker 'Ping Now' button.
    """
    from django.utils import timezone
    context = {
        "worker_status": get_worker_status(),
        "checked_at": timezone.localtime(),
    }
    return TemplateResponse(
        request, "admin/dashboard/_worker_status_bar.html", context,
    )


@staff_member_required
def check_ping_partial(request, name):
    """HTML partial — fresh probe for a single status check on
    /admin/status/. Bound to per-card 'Ping' buttons. Dispatches via
    ``CHECK_REGISTRY`` so adding a new check is a one-line registry
    update, not a new URL/view pair.
    """
    entry = CHECK_REGISTRY.get(name)
    if entry is None:
        raise Http404(f"unknown check: {name}")
    probe, title, template, ctx_key = entry
    context = {
        "name": name,
        "title": title,
        ctx_key: probe(),
    }
    return TemplateResponse(request, template, context)
