# Deploying MDProject to Railway

Step-by-step guide for deploying the Django side to Railway. Assumes
the **aggregator is already deployed** (see `aggrigator/RAILWAY.md`)
and you have its public URL handy.

## What we're deploying

| Service              | Type                                | Purpose                                          |
| -------------------- | ----------------------------------- | ------------------------------------------------ |
| `mdproject-postgres` | Railway plugin (Postgres) OR Neon   | Django ORM persistence                           |
| `mdproject-redis`    | Railway plugin (Redis)              | sessions / cache / Celery broker + result store  |
| `mdproject-web`      | Application (Dockerfile)            | gunicorn serving the WSGI app                    |
| `mdproject-worker`   | Application (**same** Dockerfile)   | Celery worker + embedded beat scheduler          |

`mdproject-web` and `mdproject-worker` are built from the **same
Dockerfile** — they just override the start command. Railway lets you
do this by creating two services pointing at the same repo with
different config files (see §5).

> **Heads-up:** the worker runs `celery worker -B` (beat embedded in
> the worker process). At MDProject's current scale this is much
> simpler than splitting into two services. **Do NOT scale the worker
> to more than 1 replica** — multiple beats would double-fire every
> task in `CELERY_BEAT_SCHEDULE`. If you outgrow this, split beat into
> its own service first (one-line entrypoint change).

---

## 0. Prerequisites

- A GitHub account with this repo pushed.
- A Railway account (sign in with GitHub — quickest).
- The aggregator already deployed at a known URL (Railway domain or
  custom). You'll need an API key from it and the webhook secret it
  prints.
- A custom domain for MDProject (optional — Railway gives you a
  `*.up.railway.app` subdomain by default).

---

## 1. Create the Postgres + Redis plugins

In the Railway project canvas:

1. **+ New → Database → Add PostgreSQL**. Railway provisions an
   instance and exposes `DATABASE_URL` as a project variable.
   (Alternatively, use Neon — same approach as the aggregator. Neon
   is cheaper at idle but requires you to assemble the URL yourself.)
2. **+ New → Database → Add Redis**. Same pattern — `REDIS_URL`
   becomes available as `${{Redis.REDIS_URL}}`.

Both plugins live on Railway's private network; the web + worker
services reach them by reference, no public ingress.

---

## 2. Create the web service

In the project canvas → **+ New → GitHub Repo** → pick this repo.
Rename to `mdproject-web`.

In **Settings**:

- **Config Path**: leave default (`railway.toml`). This file already
  configures Dockerfile build + `/healthz` healthcheck +
  `ON_FAILURE` restart policy.
- **Networking → Generate Domain**: yes (or attach your custom domain).
  Railway will route the public domain to port 8000 (matches `EXPOSE`
  in the Dockerfile).

### Environment variables

In **Variables**, set these (replace placeholders):

```
# Django core
DEBUG=False
SECRET_KEY=<openssl rand -hex 64>
ALLOWED_HOSTS=app.example.com,www.example.com,*.up.railway.app
CSRF_TRUSTED_ORIGINS=https://app.example.com,https://*.up.railway.app

# DB / Redis (reference the Railway plugins by their canonical names)
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}

# Aggregator integration
USE_AGGRIGATOR=True
# Internal Railway DNS reaches the aggregator service by its name.
# If you used a custom domain on agg-web, use that instead.
AGGRIGATOR_BASE_URL=https://agg-web-production.up.railway.app
# Long-lived service-tier API key minted in the aggregator's /admin UI
# (Aggregator → Api Keys → Create).
AGGRIGATOR_API_KEY=agg_live_<32 chars>
# Inbound webhook signing secret — paste the one printed by
# `aggrigator/scripts/register_webhook.py` after running it for this
# app's /sportgameodds/webhook URL.
AGGRIGATOR_WEBHOOK_SECRET=<from register_webhook.py>

# Email — production SMTP (Postmark / SES / Mailgun all work)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.postmarkapp.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=<smtp user>
EMAIL_HOST_PASSWORD=<smtp pass>

# Stripe (if used)
STRIPE_SECRET_KEY=
STRIPE_PUBLISHABLE_KEY=
STRIPE_WEBHOOK_SECRET=

# Tunables
MDPROJECT_WEB_WORKERS=3
MDPROJECT_WEB_TIMEOUT=30
```

> **Tip:** for the env vars shared between web and worker (everything
> except the per-process tunables), use Railway's **Project →
> Shared Variables**. Define each value once at project scope and
> reference it from both services with `${{shared.SECRET_KEY}}` etc.
> Saves you from drift the next time you rotate a secret.

Hit **Deploy**. The container will:

1. Run `python manage.py migrate --noinput`.
2. Start gunicorn on `0.0.0.0:8000`.
3. Railway's edge routes your domain to the container.

The Dockerfile already runs `collectstatic` at build time so static
files are baked into the image — whitenoise serves them at runtime.

---

## 3. Create your admin superuser

After the first successful deploy, open the web service's **Logs** tab
and use Railway's command runner (or `railway run` from the CLI):

```sh
python manage.py createsuperuser
```

Sign in at `https://<your-mdproject-domain>/admin/`.

---

## 4. Register the inbound webhook receiver

The aggregator pushes finalized/voided event payloads to MDProject's
`/sportgameodds/webhook` endpoint. From the **aggregator's** web
container terminal:

```sh
python -m aggrigator.scripts.register_webhook \
    --url https://<mdproject-domain>/sportgameodds/webhook \
    --events event.finalized,event.voided \
    --owner admin@yourdomain.com \
    --description "MDProject portal receiver"
```

Copy the printed secret into MDProject's `AGGRIGATOR_WEBHOOK_SECRET`
env var (web service Variables tab).

---

## 5. Add the worker service

In the project canvas → **+ New → GitHub Repo** → pick the **same**
repo. Rename to `mdproject-worker`.

Then in **Settings**:

- **Config Path**: `railway.worker.toml`

  This is the only Settings field you need to change manually.
  `railway.worker.toml` (in the repo root) defines the worker's start
  command, restart policy, and the disabled healthcheck — all
  version-controlled so the next operator doesn't have to remember.
  Without this override Railway would read the default `railway.toml`
  and the worker would try to come up as a second web instance.

- **Networking**: do not generate a domain — the worker has no public
  ingress.

- **Replicas**: **1**. The entrypoint runs `celery worker -B` (embedded
  beat). Two replicas would double-fire every cron in
  `CELERY_BEAT_SCHEDULE`. If you ever need to scale workers, split
  beat into its own service first.

In **Variables**, copy **all** the env vars from `mdproject-web`. The
easy path: Railway has **Project → Shared Variables**. Define each var
once at project scope and reference from both services with
`${{shared.SECRET_KEY}}` etc.

The worker doesn't expose HTTP and doesn't need `ALLOWED_HOSTS` or
`CSRF_TRUSTED_ORIGINS` strictly, but it's cheaper to share the full
env block than to maintain two near-identical lists.

Hit **Deploy**. The container has no public ingress — it just consumes
the queue and runs the beat schedule from `CELERY_BEAT_SCHEDULE`.

### Verify the worker is running

The worker prints a one-shot startup banner via `core/crons/apps.py`'s
`AppConfig.ready()` hook. Open the worker's **Deployments → Logs** —
the first ~15 lines after a deploy should look like:

```
[entrypoint] starting Celery worker (with embedded beat)...
================================================================
[celery-worker] booted — Celery beat schedule registered:
  - backend_cleanup                  task=celery.backend_cleanup  when=...
  - complete_matches_cron            task=core.crons.tasks.complete_matches_cron  when=hour=0 minute=0
  - tournament_cron_2_day_reminder   task=core.crons.tasks.tournament_cron_2_day_reminder  when=hour=0 minute=0
  - tournament_cron_bracketMaker     task=core.crons.tasks.tournament_cron_bracketMaker  when=hour=0 minute=0
[celery-worker] broker=redis://default:***@...  scheduler=django_celery_beat.schedulers:DatabaseScheduler
[celery-worker] beat is embedded (`celery worker -B`); do NOT scale this service beyond 1 replica.
================================================================
```

No banner = either the worker hasn't reached `ready()` (almost always
missing/wrong env vars — most often `REDIS_URL` not matching the one
`mdproject-web` uses), or you're on a process that's not gunicorn or
celery (we deliberately suppress the banner for `manage.py shell` etc.
to avoid log noise).

For live liveness, open `/admin/status/` once you've signed in as
staff — the worker banner pings the broker via
`celery.app.control.Inspect.ping()` and shows green within ~1s if the
worker is up, red within ~10s of it dying.

---

## 6. Pre-flight checklist

Before you mark a deploy "done", confirm:

- [ ] `https://<mdproject-domain>/healthz` returns 200.
- [ ] `https://<mdproject-domain>/admin/` requires login.
- [ ] CSRF: log in to admin, edit something, save — should NOT 403.
- [ ] Worker logs show the boot banner with all 4 beat tasks listed.
- [ ] `/admin/status/` shows the worker banner green ("worker(s) online").
- [ ] Aggregator's `event.finalized` webhook reaches
      `/sportgameodds/webhook` (POST with valid signature → 200).

---

## 7. Troubleshooting

**`alembic` / migrate hangs forever:** the worker may be racing the
web container for the schema lock. The entrypoint's `worker` branch
deliberately does NOT re-run migrations for this reason — but if both
services started simultaneously and the web container's migrate took
unusually long, the worker may time out waiting on the lock. Set the
worker service to depend on `mdproject-web` becoming healthy
(Railway: Service → Settings → "Wait for" → mdproject-web).

**Worker boots but no tasks fire:** confirm `REDIS_URL` matches between
web and worker. Celery's broker is `${REDIS_URL}/0` — if web writes to
one Redis and worker reads from another, tasks queue but never run.
The boot banner prints the (redacted) broker URL — compare it to
what you set on `mdproject-web`.

**Webhook 401s:** `AGGRIGATOR_WEBHOOK_SECRET` doesn't match the secret
the aggregator stored when you ran `register_webhook.py`. Re-run that
script with `--rotate` and update MDProject's env var.

**`SECRET_KEY` warning at startup:** `settings.py` raises in production
if `SECRET_KEY` is unset. Set it via env or Shared Variables; Railway
won't restart the container until the var is present.
