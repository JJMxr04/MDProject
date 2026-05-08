#!/bin/sh
# MDProject container entrypoint. One image, multiple roles — Coolify /
# Railway deploy each role as its own service pointing at this image with
# a different first arg.
#
#   web          — apply migrations then start gunicorn (the Django app)
#   worker       — start Celery worker with embedded beat scheduler
#                  (one process handles both task execution AND scheduling)
#   migrate-only — run migrations and exit (one-shot job, e.g. CI / preview)
#   anything else — exec it directly (debug: ``sh``, ``python manage.py shell``)
#
# Why worker+beat in one process: at MDProject's current scale a single
# Celery worker with `-B` (embedded beat) is operationally simpler than
# splitting them into two services — one less env-var copy, one less
# Railway service to keep healthy. The DatabaseScheduler keeps the beat
# schedule in Postgres (django-celery-beat), so swapping to a separate
# beat service later is a one-line entrypoint change with no data
# migration. Don't run more than ONE worker replica with `-B` — multiple
# beats would double-fire every scheduled task.
set -e

ROLE="${1:-web}"

case "$ROLE" in
  web)
    echo "[entrypoint] applying Django migrations..."
    python manage.py migrate --noinput

    echo "[entrypoint] starting gunicorn..."
    # Sync workers — Django doesn't need ASGI here. ``access-logfile -``
    # routes access logs to stdout for journald / Coolify / Railway logs.
    exec gunicorn CoreRoot.wsgi:application \
        --workers "${MDPROJECT_WEB_WORKERS:-3}" \
        --bind 0.0.0.0:8000 \
        --timeout "${MDPROJECT_WEB_TIMEOUT:-30}" \
        --graceful-timeout 30 \
        --access-logfile - \
        --error-logfile -
    ;;

  worker)
    echo "[entrypoint] starting Celery worker (with embedded beat)..."
    # Migrations run on the web container; the worker waits for that to
    # finish via the Railway / Coolify dependency setting. We do NOT
    # re-run migrations here — racing two services for the schema lock
    # is the leading cause of "migrate hangs forever" reports.
    #
    # `-B` embeds the beat scheduler in the same process. Single-replica
    # only — multiple workers with -B would double-fire every cron.
    # Concurrency defaults to 2; tune via MDPROJECT_WORKER_CONCURRENCY.
    exec celery -A CoreRoot worker \
        --beat \
        --scheduler django_celery_beat.schedulers:DatabaseScheduler \
        --loglevel "${MDPROJECT_WORKER_LOGLEVEL:-info}" \
        --concurrency "${MDPROJECT_WORKER_CONCURRENCY:-2}"
    ;;

  migrate-only)
    echo "[entrypoint] running migrate and exiting..."
    exec python manage.py migrate --noinput
    ;;

  *)
    exec "$@"
    ;;
esac
