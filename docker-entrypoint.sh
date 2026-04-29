#!/bin/sh
# MDProject container entrypoint. Django side is single-role for now (web).
#
#   web          — apply migrations then start gunicorn
#   migrate-only — run migrations and exit (one-shot job)
#   anything else — exec it directly (debug: ``sh``, ``python manage.py shell``)
set -e

ROLE="${1:-web}"

case "$ROLE" in
  web)
    echo "[entrypoint] applying Django migrations..."
    python manage.py migrate --noinput

    echo "[entrypoint] starting gunicorn..."
    # Sync workers — Django doesn't need ASGI here. ``access-logfile -``
    # routes access logs to stdout for journald / Coolify logs.
    exec gunicorn CoreRoot.wsgi:application \
        --workers "${MDPROJECT_WEB_WORKERS:-3}" \
        --bind 0.0.0.0:8000 \
        --timeout "${MDPROJECT_WEB_TIMEOUT:-30}" \
        --graceful-timeout 30 \
        --access-logfile - \
        --error-logfile -
    ;;

  migrate-only)
    echo "[entrypoint] running migrate and exiting..."
    exec python manage.py migrate --noinput
    ;;

  *)
    exec "$@"
    ;;
esac
