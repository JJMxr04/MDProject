# Deploying MDProject to Coolify

Step-by-step guide for deploying the Django side to Coolify (self-hosted,
behind Traefik). Assumes the **aggregator is already deployed**
(see `aggrigator/COOLIFY.md`) and you have its internal/public URL handy.

## What we're deploying

| Service             | Type                        | Purpose                                          |
| ------------------- | --------------------------- | ------------------------------------------------ |
| `mdproject-pg`      | Coolify resource (Postgres) | Django ORM + Procrastinate task queue + cache    |
| `mdproject-web`     | Application (Dockerfile)    | gunicorn serving the WSGI app                    |
| `mdproject-worker`  | Application (Dockerfile)    | Procrastinate worker (task execution + schedule) |

No Redis — task queue, periodic schedule, and Django cache all live in
Postgres now (Procrastinate uses LISTEN/NOTIFY for push delivery; cache
uses `django.core.cache.backends.db.DatabaseCache`).

`mdproject-web` and `mdproject-worker` are built from the **same
Dockerfile in this repo** — they just override `CMD`. The entrypoint
dispatches on `$1` (`web` runs migrate-then-gunicorn; `worker` runs
`python manage.py procrastinate worker`).

---

## 1. Create the Postgres resource

Coolify → **Resources → New Resource → Postgres** (version 18).

Note the **internal** connection URL from the resource page (something
like `postgres://USER:PASS@HOST:5432/DBNAME`). Use the internal hostname,
not the public one — both apps reach the DB over Coolify's internal
network. This single URL is pasted into both the web and worker
Applications below.

---

## 2. Create the `mdproject-web` Application

Coolify → **Applications → New Application**:

- **Source**: this repo (Git URL).
- **Build pack**: `Dockerfile` (auto-detects).
- **Port**: `8000` (matches `EXPOSE` in the Dockerfile).
- **Health check path**: `/healthz`.
- **Custom CMD**: **leave empty.** The Dockerfile's `CMD ["web"]`
  triggers `docker-entrypoint.sh web` — migrate, createcachetable,
  then gunicorn.

### Environment variables for `mdproject-web`

Generate secrets first:

```sh
openssl rand -hex 64    # SECRET_KEY
openssl rand -hex 32    # AGGRIGATOR_WEBHOOK_SECRET   (must match aggregator's AGG_WEBHOOK_SECRET)
openssl rand -hex 32    # PARADISE_SECRET             (must match aggregator's AGG_PARADISE_SECRET)
```

```
# --- Django core ---
DEBUG=False
SECRET_KEY=<openssl rand -hex 64>
ALLOWED_HOSTS=app.example.com,www.example.com           # comma-separated; bare hostnames
CSRF_TRUSTED_ORIGINS=https://app.example.com            # full origin (scheme + host); also accepts bare host (auto-prefixed)

# --- Database (use the INTERNAL Postgres host from Coolify) ---
DATABASE_URL=postgres://USER:PASS@PG_HOST:5432/DBNAME

# --- Aggregator integration ---
USE_AGGRIGATOR=True
# Internal Coolify DNS reaches the aggregator service by its Application
# name (or use its custom domain — both work).
AGGRIGATOR_BASE_URL=https://aggregator.example.com
# HMAC secrets shared with the aggregator. Web fails to boot if either
# is missing while USE_AGGRIGATOR=True (settings.py:754-759).
AGGRIGATOR_WEBHOOK_SECRET=<same value as AGG_WEBHOOK_SECRET on aggregator>
PARADISE_SECRET=<same value as AGG_PARADISE_SECRET on aggregator>

# --- Email — Resend over HTTPS (port 443) ---
# SMTP is blocked from most container hosts, so we send via Resend's REST
# API. Get a key from https://resend.com → API Keys.
RESEND_API_KEY=<your Resend API key>
DEFAULT_FROM_EMAIL=noreply@yourdomain.com

# --- Stripe (if billing is enabled) ---
STRIPE_SECRET_KEY=
STRIPE_PUBLISHABLE_KEY=
STRIPE_WEBHOOK_SECRET=
PLATFORM_COST=                                          # e.g. 2.99 — PRO monthly price in dollars

# --- S3 for user uploads (avatars, media) ---
# MEDIA_URL is hardcoded to the S3 bucket in settings.py, so these are
# effectively required if users upload anything.
BUCKETEER_AWS_ACCESS_KEY_ID=
BUCKETEER_AWS_SECRET_ACCESS_KEY=
BUCKETEER_BUCKET_NAME=
BUCKETEER_AWS_REGION=

# --- Analytics gate (pair with aggregator's matching flag) ---
ANALYTICS_FREE_FOR_ALL=1

# --- Gunicorn knobs ---
MDPROJECT_WEB_WORKERS=3
MDPROJECT_WEB_TIMEOUT=30

# --- django-silk profiler (off in prod; flip on temporarily for debug) ---
SILK_ENABLED=false
SILK_INTERCEPT_PERCENT=5
```

Hit **Deploy.** The container will:

1. Run `python manage.py migrate --noinput`.
2. Run `python manage.py createcachetable` (idempotent; creates
   `django_cache` for the DatabaseCache backend).
3. Start gunicorn on `0.0.0.0:8000`.
4. Coolify's Traefik routes the public domain to `mdproject-web:8000`.

The Dockerfile already runs `collectstatic` at build time, so static
files are baked into the image and whitenoise serves them at runtime.

---

## 3. Create the `mdproject-worker` Application

Coolify → **Applications → New Application** (point at the **same**
Git source / branch, **same** Dockerfile):

- **Port**: leave empty (no ingress; worker doesn't serve HTTP).
- **Custom CMD**: `worker`
- **Health check**: disable (no HTTP listener to probe).
- **Public domain**: none.

### Environment variables for `mdproject-worker`

Paste **the same env-var block as `mdproject-web`** with these
exceptions:

- Web-only knobs (`MDPROJECT_WEB_WORKERS`, `MDPROJECT_WEB_TIMEOUT`,
  `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `SILK_*`) are no-ops here —
  omit or leave; harmless either way.
- Add a worker-only knob:

```
MDPROJECT_WORKER_CONCURRENCY=2          # parallel jobs per worker process
```

- Use the **same** `DATABASE_URL`, **same** secrets, **same** Resend key,
  **same** `ANALYTICS_FREE_FOR_ALL`.

Hit **Deploy.** Worker logs should show:

```
[entrypoint] starting Procrastinate worker...
```

followed by Procrastinate registering the periodic schedule
(`@app.periodic(cron=...)` decorators on each task in `core/crons/`).

> **Migrations only run on `mdproject-web`.** The worker entrypoint
> deliberately does NOT re-run migrate — racing two services for the
> schema lock is the leading cause of "migrate hangs forever" reports.
> Deploy `mdproject-web` first on a fresh DB so the tables exist before
> the worker tries to LISTEN on `procrastinate_jobs`.

---

## 4. Post-deploy: create the superuser

From the `mdproject-web` Coolify Terminal tab:

```sh
python manage.py createsuperuser
```

Then sign in at `https://<your-domain>/admin/`.

---

## 5. Approve a waitlist entry so you can register a real user

1. Visit `https://<your-domain>/auth/waitlist/` and submit your email.
2. In Django admin (`/admin/core_auth/waitlistentry/`), open the entry
   and tick **Admin granted access**, then save.
3. Go to `https://<your-domain>/auth/signup/` and register with that
   email. The form's `clean_email` will accept you.

---

## 6. Wire the webhook between aggregator and MDProject

The aggregator collapsed to single-tenant — there is no
`register_webhook` script. The pairing is **pure env vars**:

| On the aggregator (`agg-web` + `agg-worker`) | On MDProject (`mdproject-web` + `mdproject-worker`) |
| -------------------------------------------- | --------------------------------------------------- |
| `AGG_MDPROJECT_URL=https://<mdproject-domain>` | (n/a)                                             |
| `AGG_WEBHOOK_SECRET=<shared secret>`         | `AGGRIGATOR_WEBHOOK_SECRET=<same shared secret>`    |
| `AGG_PARADISE_SECRET=<shared secret>`        | `PARADISE_SECRET=<same shared secret>`              |

The aggregator appends its hardcoded receiver path
(`/sportgameodds/webhook`) to `AGG_MDPROJECT_URL`. To rotate either
shared secret: update both sides in Coolify and restart all four
applications.

---

## 7. Coolify-specific knobs

- **Migrations**: run inside the web container's entrypoint on every
  boot (`docker-entrypoint.sh web` → `migrate` + `createcachetable`).
  Coolify has no equivalent of Railway's `preDeployCommand`, so we rely
  on this in-entrypoint step. Idempotent; multiple boots are safe.
- **Persistent storage**: only Postgres needs a volume. Coolify's
  Postgres resource handles that automatically. Don't bind-mount the
  app container.
- **Static files**: baked into the image via `collectstatic` at build
  time. If you change static files, just redeploy.
- **Media uploads**: user-uploaded files go to S3 via `django-storages`
  (set the `BUCKETEER_*` env vars). MDProject's `MEDIA_URL` is
  hardcoded to the S3 bucket in settings.py — without the env vars it
  will resolve to `https://None.s3.amazonaws.com/`.
- **Logs**: stdout / stderr go to Coolify's **Logs** tab per app.
- **Rolling deploys**: Dockerfile's `HEALTHCHECK` is honored — the old
  container stays up until `/healthz` returns 200 on the new one.
- **Horizontal scale**: web is stateless. The worker can scale to
  multiple replicas safely (Procrastinate uses row-level locks on
  `procrastinate_periodic_defers` to cooperate), but at this app's
  volume there's no reason to scale either above 1.

---

## 8. Pre-flight checklist

- [ ] `https://<mdproject-domain>/healthz` returns `{"ok": true}`.
- [ ] `https://<mdproject-domain>/robots.txt` lists the public marketing
      paths under `Allow:` and disallows `/web/`, `/admin/`, `/api/`,
      `/auth/` (sub-paths), etc.
- [ ] `https://<mdproject-domain>/web/portal/match/me/` returns
      `X-Robots-Tag: noindex, nofollow, noarchive` (curl with `-I`).
- [ ] `https://<mdproject-domain>/about/` does NOT return that header.
- [ ] `https://<mdproject-domain>/auth/signup/` rejects emails not on
      the waitlist.
- [ ] Worker logs show `starting Procrastinate worker...` and the
      periodic schedule registering.
- [ ] Webhook from aggregator hits `/sportgameodds/webhook` with status
      200 (check the aggregator's `/admin` webhook-deliveries view).
- [ ] An accepted match auto-creates a Golden Game (queries the
      aggregator's `/v1/events` — confirms outbound integration).

---

## 9. Troubleshooting

**`SECRET_KEY must be set in production`** at startup → you set
`DEBUG=False` but didn't set `SECRET_KEY`. Add it to Coolify env vars.

**`ALLOWED_HOSTS must be a non-empty list`** at startup → same shape.
Coolify's auto-assigned domain is NOT auto-merged; list every hostname
the app answers on.

**`AGGRIGATOR_WEBHOOK_SECRET must be set when USE_AGGRIGATOR=True`** →
hard-fail at boot. Either set the secret or temporarily flip
`USE_AGGRIGATOR=False` to bring the app up.

**`PARADISE_SECRET must be set when USE_AGGRIGATOR=True`** → same shape,
different secret.

**`CSRF verification failed`** on form POSTs → set
`CSRF_TRUSTED_ORIGINS` to include your full HTTPS origin
(`https://app.example.com`). Required when behind Traefik. Bare
hostnames are auto-prefixed with `https://` by settings.py.

**Static files 404 in production** → check the build logs for the
`collectstatic` step. Whitenoise serves from `STATIC_ROOT` — if empty,
every asset 404s.

**`SECURE_SSL_REDIRECT` infinite loop** → `SECURE_PROXY_SSL_HEADER` not
honored. We set it to `("HTTP_X_FORWARDED_PROTO", "https")` which
matches Coolify's Traefik. If you fronted Coolify with another proxy
that uses a different header, override `SECURE_PROXY_SSL_HEADER` in
your env-driven settings.

**Match-create flow returns "No events scheduled..."** → MDProject can't
reach the aggregator. From the `mdproject-web` Terminal tab:
`curl https://<aggregator-domain>/healthz` — if it fails, fix
`AGGRIGATOR_BASE_URL` or the aggregator's networking.

**Worker logs spew `connection refused` on Postgres** → the worker
container probably started before web finished migrating. Coolify will
restart it; once migrations are done it'll stay up. On a fresh DB,
deploy `mdproject-web` first.

**`migrate` hangs forever on deploy** → likely a schema-lock race
because both web and worker tried to run migrations. The worker
entrypoint deliberately doesn't, so this only happens if you manually
ran `migrate` from the worker terminal during a web redeploy. Wait for
both to settle, then trigger a fresh web deploy.
