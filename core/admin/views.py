from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.template.response import TemplateResponse

from core.admin.status import (
    check_aggregator,
    check_db,
    check_redis,
    get_beat_schedule,
    get_recent_results,
    get_worker_status,
)


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
        ("Postgres", check_db()),
        ("Redis (cache + broker)", check_redis()),
        ("Aggregator", check_aggregator()),
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
def status_worker_partial(request):
    """HTML partial with just the worker banner — JS poll target.

    Returned as a fragment (no <html>/<body>) so the polling JS can
    swap it into the banner container directly. Same auth gate as the
    full page.
    """
    context = {"worker": get_worker_status()}
    return TemplateResponse(request, "admin/status/_worker_banner.html", context)
