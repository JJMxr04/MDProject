# syntax=docker/dockerfile:1.6
#
# MDProject (Django) container — used by Coolify (Application type: Dockerfile).
# Single role: gunicorn serving the WSGI app. Whitenoise serves the static
# files baked at image-build time. Postgres + Redis are external (Coolify
# resources or the managed DB pointed at via DATABASE_URL).

# ---------- builder ----------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

# psycopg2 wheel needs libpq-dev + build-essential at install time.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cache the deps layer.
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install --prefix=/install -r requirements.txt

# ---------- runtime ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=CoreRoot.settings

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --no-create-home --shell /bin/false app

COPY --from=builder /install /usr/local

WORKDIR /app

# Copy code last so source edits don't bust the deps layer.
COPY --chown=app:app . /app

# Run collectstatic at build time so the running container is read-only.
# Dummy env vars satisfy settings.py's production-mode startup guards
# (it raises if SECRET_KEY/ALLOWED_HOSTS are missing while DEBUG=False).
# A throwaway sqlite DATABASE_URL keeps dj_database_url happy.
#
# SILK_ENABLED=true at build time so django-silk's static files (its
# JS/CSS/images at silk/static/silk/...) get collected into STATIC_ROOT.
# The runtime decides separately whether to install silk's middleware +
# URL routes via its own SILK_ENABLED env. If runtime silk is off, the
# extra static files are inert; if it's on (the prod debug case), they
# need to already exist in staticfiles/ or every asset 404s.
#
# No `|| true` here — any failure must bubble up; a silent empty
# staticfiles/ ships a broken image. The rm cleanup below tolerates
# absent dev-only paths.
RUN DEBUG=False \
    SECRET_KEY=collectstatic-build-time-only \
    ALLOWED_HOSTS=localhost \
    DATABASE_URL=sqlite:///tmp/build.sqlite3 \
    SILK_ENABLED=true \
    python manage.py collectstatic --noinput

RUN rm -rf .git/ .vscode/ .pytest_cache/ tests/ /tmp/build.sqlite3 2>/dev/null || true \
    && chmod +x /app/docker-entrypoint.sh

USER app

EXPOSE 8000

# Coolify reads HEALTHCHECK to gate rolling deploys. /healthz is added by
# core/views.py and routed in CoreRoot/urls.py.
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]

CMD ["web"]
