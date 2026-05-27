#!/bin/sh
# MDProject container entrypoint. One image, multiple roles — Coolify /
# Railway deploy each role as its own service pointing at this image with
# a different first arg.
#
#   web          — apply migrations then start gunicorn (the Django app)
#   worker       — start the Procrastinate worker (task execution +
#                  in-process periodic scheduler)
#   migrate-only — run migrations and exit (one-shot job, e.g. CI / preview)
#   anything else — exec it directly (debug: ``sh``, ``python manage.py shell``)
#
# Procrastinate runs ONE process that handles both task execution and the
# periodic schedule (declared via @app.periodic decorators on each task).
# The schedule is in-process; multiple worker replicas would each compete
# to claim the same periodic job via Postgres row-level locks, so safe to
# scale horizontally (unlike Celery's separate beat process). At this app's
# scale we still run a single replica — see railway.worker.toml.
set -e

ROLE="${1:-web}"

case "$ROLE" in
  web)
    echo "[entrypoint] applying Django migrations..."
    python manage.py migrate --noinput

    # Idempotent — succeeds with "Cache table 'django_cache' already
    # exists." on every redeploy after the first. Required for the
    # DatabaseCache backend introduced when we cut Redis.
    echo "[entrypoint] ensuring cache table..."
    python manage.py createcachetable

    echo "[entrypoint] starting gunicorn..."
    # Sync workers — Django doesn't need ASGI here. ``access-logfile -``
    # routes access logs to stdout for journald / Coolify / Railway logs.
    # ``--forwarded-allow-ips=*`` makes gunicorn trust X-Forwarded-* headers
    # from Coolify's Traefik. Without it gunicorn strips ``X-Forwarded-Proto:
    # https`` (defaulting to trust only 127.0.0.1), Django's
    # ``SECURE_PROXY_SSL_HEADER`` never sees ``https``, ``request.is_secure()``
    # returns False, ``SECURE_SSL_REDIRECT`` fires a 301 to https://... and
    # the browser ends up in an infinite loop. Trusting "*" is safe because
    # Coolify's edge proxy is the only thing that can reach the container;
    # external clients never bypass it.
    exec gunicorn CoreRoot.wsgi:application \
        --workers "${MDPROJECT_WEB_WORKERS:-3}" \
        --bind "0.0.0.0:${PORT:-8000}" \
        --timeout "${MDPROJECT_WEB_TIMEOUT:-30}" \
        --graceful-timeout 30 \
        --forwarded-allow-ips="*" \
        --access-logfile - \
        --error-logfile -
    ;;

  worker)
    echo "[entrypoint] starting Procrastinate worker..."
    # Migrations run on the web container; the worker waits for that to
    # finish via the Railway / Coolify dependency setting. We do NOT
    # re-run migrations here — racing two services for the schema lock
    # is the leading cause of "migrate hangs forever" reports.
    #
    # --concurrency tunes how many jobs run in parallel within this
    # process. The Procrastinate worker uses Postgres LISTEN/NOTIFY for
    # push-based job delivery (no polling), so a small concurrency is
    # plenty for this app's volume.
    exec python manage.py procrastinate worker \
        --concurrency "${MDPROJECT_WORKER_CONCURRENCY:-2}"
    ;;

  migrate-only)
    echo "[entrypoint] running migrate and exiting..."
    python manage.py migrate --noinput
    exec python manage.py createcachetable
    ;;

  *)
    exec "$@"
    ;;
esac
