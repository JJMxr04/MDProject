# Deploying MDProject to Coolify

Step-by-step guide for deploying the Django side to Coolify (self-hosted,
behind Traefik). Assumes the **aggregator is already deployed**
(see `aggrigator/COOLIFY.md`) and you have its public URL handy.

## What we're deploying

| Service           | Type                        | Purpose                                |
| ----------------- | --------------------------- | -------------------------------------- |
| `mdproject-pg`    | Coolify resource (Postgres) | Django ORM persistence                 |
| `mdproject-redis` | Coolify resource (Redis)    | session / cache / Celery (if enabled)  |
| `mdproject-web`   | Application (Dockerfile)    | gunicorn serving the WSGI app          |

No worker container yet — the legacy Celery beat schedule mostly went away
during the aggregator cutover. If you need it back, mirror the aggregator
worker pattern: same Dockerfile, override `CMD` with `celery -A CoreRoot worker`.

---

## 1. Create the resources

Same as the aggregator side — Coolify → **Resources**:

1. **New Resource → Postgres** (version 18). Note the connection URL.
2. **New Resource → Redis** (version 7). Note the URL.

---

## 2. Create the web Application

Coolify → **Applications → New Application**:

- **Source**: this repo (Git URL).
- **Build pack**: `Dockerfile`.
- **Port**: `8000` (matches `EXPOSE` in the Dockerfile).
- **Health check path**: `/healthz`.

### Environment variables

```
# Django core
DEBUG=False
SECRET_KEY=<openssl rand -hex 64>
ALLOWED_HOSTS=app.example.com,www.example.com    # comma-separated
CSRF_TRUSTED_ORIGINS=https://app.example.com     # full origin (scheme + host)

# DB / Redis (paste from Coolify resource pages)
DATABASE_URL=postgres://<user>:<pass>@<coolify-pg-host>:5432/<db>?sslmode=require
REDIS_URL=redis://<coolify-redis-host>:6379

# Aggregator integration
USE_AGGRIGATOR=True
# Internal Coolify network DNS reaches the aggregator service by its
# Application name. If you used a custom domain, use that:
AGGRIGATOR_BASE_URL=https://aggregator.example.com
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

# S3 for user avatars / static (if you don't want to bake static into the
# image — image already does collectstatic + whitenoise so this is optional)
BUCKETEER_AWS_ACCESS_KEY_ID=
BUCKETEER_AWS_SECRET_ACCESS_KEY=
BUCKETEER_BUCKET_NAME=
BUCKETEER_AWS_REGION=

# Tunables
MDPROJECT_WEB_WORKERS=3
MDPROJECT_WEB_TIMEOUT=30
```

Hit **Deploy**. The container will:

1. Run `python manage.py migrate --noinput`.
2. Start gunicorn on `0.0.0.0:8000`.
3. Coolify's Traefik routes the public domain to `mdproject-web:8000`.

The Dockerfile already runs `collectstatic` at build time so static
files are baked into the image — whitenoise serves them at runtime.

---

## 3. After first deploy: create your superuser

From the Coolify Terminal tab on `mdproject-web`:

```sh
python manage.py createsuperuser
```

Then sign in at `https://<your-domain>/admin/`.

---

## 4. Approve a waitlist entry so you can register a real user

1. Visit `https://<your-domain>/auth/waitlist/` and submit your email.
2. In Django admin (`/admin/auth/waitlistentry/`), open the entry and
   tick **Admin granted access**, then save.
3. Go to `https://<your-domain>/auth/signup/` and register with that
   email. The form's `clean_email` will accept you.

---

## 5. Register the webhook secret

If you haven't already, run from inside the **aggregator** Coolify
Terminal:

```sh
python -m aggrigator.scripts.register_webhook \
    --url https://<mdproject-domain>/sportgameodds/webhook \
    --events event.finalized,event.voided \
    --owner admin@yourdomain.com \
    --description "MDProject portal receiver"
```

Copy the printed secret into MDProject's `AGGRIGATOR_WEBHOOK_SECRET` env
var (Coolify env vars on the `mdproject-web` Application). Restart the
app from Coolify to pick up the new env value.

---

## 6. Coolify-specific knobs

- **Persistent storage**: only Postgres needs a volume — handled by
  Coolify's Postgres resource. Don't bind-mount the app container.
- **Static files**: baked into the image via `collectstatic` at build
  time. If you change static files, just redeploy.
- **Media uploads**: by default, user-uploaded files go to a local
  filesystem inside the container — they vanish on redeploy. Production
  should use S3 (set the `BUCKETEER_*` env vars; `django-storages` is
  already in `requirements.txt`).
- **Logs**: stdout / stderr go to Coolify's **Logs** tab.
- **Rolling deploys**: Dockerfile's HEALTHCHECK is honored — old
  container stays up until `/healthz` returns 200 on the new one.
- **Migrations**: run automatically on every deploy via the entrypoint.
  Idempotent. If you need to run a specific migration manually, use
  the Terminal tab: `python manage.py migrate <app> <migration_name>`.

---

## 7. Pre-flight checklist

- [ ] `https://<mdproject-domain>/healthz` returns `{"ok": true}`.
- [ ] `https://<mdproject-domain>/robots.txt` lists the public marketing
      paths under `Allow:` and disallows `/web/`, `/admin/`, `/api/`,
      `/auth/` (sub-paths), etc.
- [ ] `https://<mdproject-domain>/web/portal/match/me/` returns
      `X-Robots-Tag: noindex, nofollow, noarchive` (curl with `-I`).
- [ ] `https://<mdproject-domain>/about/` does NOT return that header.
- [ ] `https://<mdproject-domain>/auth/signup/` rejects emails not on
      the waitlist.
- [ ] Webhook from aggregator hits `/sportgameodds/webhook` with status
      200 (check aggregator's `/admin/webhook-deliveries`).
- [ ] An accepted match auto-creates a Golden Game (queries the
      aggregator's `/v1/events` — confirms the integration works).

---

## 8. Troubleshooting

**`SECRET_KEY must be set in production`** at startup → you set
`DEBUG=False` but didn't set `SECRET_KEY`. Add it to Coolify env vars.

**`ALLOWED_HOSTS must be a non-empty list`** at startup → same shape.

**`CSRF verification failed`** on form POSTs → set
`CSRF_TRUSTED_ORIGINS` to include your full HTTPS origin
(`https://app.example.com`). Required when behind Traefik.

**Static files 404 in production** → ensure the Dockerfile build ran
`collectstatic` (check the build logs). Whitenoise serves from
`STATIC_ROOT` — if empty, you'll get 404s.

**`SECURE_SSL_REDIRECT` infinite loop** → `SECURE_PROXY_SSL_HEADER` not
honored. We set it to `("HTTP_X_FORWARDED_PROTO", "https")` which
matches Coolify's Traefik. If you fronted Coolify with another proxy
that uses a different header, override `SECURE_PROXY_SSL_HEADER` in
your env-driven settings.

**Match-create flow returns "No events scheduled..."** → MDProject can't
reach the aggregator. From the Terminal tab:
`curl https://<aggregator-domain>/healthz` — if it fails, fix
`AGGRIGATOR_BASE_URL` or the aggregator's networking.
