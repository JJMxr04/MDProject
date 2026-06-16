from django.urls import path

from core.admin.admin import custom_admin_view
from core.admin.views import (
    backfill_logos,
    check_ping_partial,
    redis_ping_partial,
    run_task,
    status_page,
    status_worker_partial,
    stripe_setup_page,
    worker_ping_partial,
)

app_name = 'core-admin'

urlpatterns = [
    path('dashboard/', custom_admin_view, name='admin_dashboard'),
    # Project status — worker liveness + DB / Redis / aggregator
    # health + live beat schedule + recent task results. Admin-only
    # via @staff_member_required on the view.
    path('status/', status_page, name='admin_status'),
    path('status/worker/', status_worker_partial, name='admin_status_worker'),
    # Manually queue a registered periodic task (POST, staff-only).
    path('status/run-task/', run_task, name='admin_run_task'),
    # Backfill team logos — enqueue a crest fetch for every team
    # missing an ok logo (POST, staff-only).
    path('status/backfill-logos/', backfill_logos, name='admin_backfill_logos'),
    path('redis-ping/', redis_ping_partial, name='admin_redis_ping'),
    path('worker-ping/', worker_ping_partial, name='admin_worker_ping'),
    # /admin/check-ping/<name>/ — per-card manual ping on /admin/status/.
    # `name` ∈ {postgres, redis, aggregator, worker} (see CHECK_REGISTRY
    # in core/admin/views.py).
    path('check-ping/<str:name>/', check_ping_partial, name='admin_check_ping'),
    # One-click Stripe setup — account status, API version detection,
    # webhook endpoint create. Admin-only via the view's decorator.
    path('stripe-setup/', stripe_setup_page, name='admin_stripe_setup'),
]
