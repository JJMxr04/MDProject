# MDProject — Management Commands & Deploy Reference

Every custom `manage.py` command in the project, what it does, and how it ties
into deploys. Run any of these with:

```bash
python manage.py <command> [flags]
# in a running container:
docker exec -it <web-container> python manage.py <command>
```

> **TL;DR for a normal deploy:** you don't run anything by hand. The container
> entrypoint runs `migrate`, `createcachetable`, and `bootstrap_periodic`
> automatically (see [Deploy flow](#deploy-flow)). The only manual,
> environment-level setup is **env vars** + the **Stripe webhook** (one-time per
> host — see [New host checklist](#new-host--first-deploy-checklist)).

---

## Command reference

### 🚀 Deploy / bootstrap (run automatically on deploy)

| Command | What it does | Safe to re-run |
|---|---|---|
| **`bootstrap_periodic`** | Runs the **idempotent** recurring tasks once, so state exists immediately instead of waiting for the midnight cron. Steps: **seed billing plans** → ensure today's **Pick of the Day** → **season lifecycle** → complete due matches → sync POTD results → expire stale invites → reconcile subscriptions. Each step is isolated (one failure never aborts the rest). **Skips** the two date-windowed tournament tasks (bracket maker, 2-day reminder) — re-firing those would duplicate brackets / re-send emails. | ✅ get-or-create, never duplicates |

`core/commands/management/commands/bootstrap_periodic.py`. Called (backgrounded)
by `docker-entrypoint.sh` in the **web** role.

### 💳 Billing / Stripe

| Command | What it does | Notes |
|---|---|---|
| **`seed_billing_plans`** | **Get-or-create the FREE + PRO `Plan` rows**, pricing PRO from the `PLATFORM_COST` env var. Saving PRO fires the `post_save` signal that pushes the Product + Price to Stripe. This replaces creating plans by hand in the admin. | ✅ idempotent. Runs automatically inside `bootstrap_periodic`. Needs `STRIPE_SECRET_KEY` set for the Stripe push to populate `stripe_price_id`. |
| **`sync_platform_cost`** | Reconciles **just the PRO price** with `PLATFORM_COST` (env is dollars; stored as cents). Re-save mints a new immutable Stripe Price and archives the old. | Run after changing `PLATFORM_COST` if you don't want to wait for the next deploy. (`seed_billing_plans` also reconciles price, so a redeploy does this too.) |
| **`backfill_aggrigator_users`** | One-shot: mirror every existing User into the aggregator + ensure a FREE Subscription row. | Flags: `--dry-run`, `--batch-size 50`, `--sleep 0.1`. Run once after enabling the aggregator integration. |
| **`reset_stripe_customers`** | Force every user onto a freshly-minted Stripe Customer. **Destructive to billing links.** | Refuses to run without `--yes`. `--dry-run` to preview, `--exclude-staff`, `--sleep` to throttle. Recovery/migration tool only. |

### ⭐ Pick of the Day

| Command | What it does | Notes |
|---|---|---|
| **`curate_potd`** | Ensure **today's** Pick of the Day exists (get-or-create). Reports "no viable fixture" without failing when the catalog is empty. | ✅ idempotent. Also runs inside `bootstrap_periodic`; the nightly cron `core.potd.curate_pick_of_day` (00:10) keeps it going. |

### 🏟️ Catalog / sports data

| Command | What it does | Notes |
|---|---|---|
| **`seed_sports_leagues`** | Seed/refresh the **Sport + League** tables from SportsGameOdds (2 API calls), with per-league refresh cadences. | Run **once on a fresh DB** (events/POTD need leagues) and when adding leagues. Flags: `--activate <leagueIDs…>`, `--deactivate-others`. |

### 👥 Auth / groups

| Command | What it does | Notes |
|---|---|---|
| **`create_portal_group`** | Get-or-create the `Portal Group` auth group. | ✅ idempotent. Run once on a fresh DB if you rely on that group for permissions. |

### 📊 Metrics (read-only)

| Command | What it does | Notes |
|---|---|---|
| **`metrics_report`** | Prints D1/D7 retention, picks/user/week, both-players-return (from `ProductEvent`). | Read-only. `--days 14` (default). |

### 🌱 Dev seed data

| Command | What it does | Notes |
|---|---|---|
| **`seed_portal`** | Seed the dev DB with realistic users/matches/tournaments. | Dev only. `--users 20 --tournaments 8 --matches 40`. `--reset` requires `DEBUG=True`. |

### ☢️ Destructive — local dev only

| Command | What it does | Notes |
|---|---|---|
| **`reset_db`** | Drops and recreates **all** tables. | **No safety flag — wipes the DB.** Never run against prod. |
| **`flush_except`** | `TRUNCATE … RESTART IDENTITY CASCADE` every table **except** the ones you name. | **Destructive.** `flush_except <table> [<table> …]`. Local only. |

---

## Deploy flow

The same image runs multiple roles; `docker-entrypoint.sh` picks the role from
the first arg (Coolify/Railway deploy each as its own service).

| Role | What the entrypoint runs |
|---|---|
| **web** (default) | `migrate` → `createcachetable` → **`bootstrap_periodic`** (backgrounded, non-blocking) → `gunicorn` |
| **worker** | `procrastinate worker` — **this is what runs the crons** (see below). No migrations here. |
| **migrate-only** | `migrate` → `createcachetable`, then exit (CI / preview jobs) |

So on every deploy of the **web** service, the billing plans + Pick of the Day +
due settlements are ensured automatically (idempotent). **Static files** are
collected at **image build time** (in the Dockerfile), not the entrypoint.

### Crons are run by the Procrastinate **worker** — not Celery

Schedules live in code via `@app.periodic(cron=…)` decorators
(`core/crons/tasks.py`, `core/potd/tasks.py`), executed by the **worker service**
(`procrastinate worker`). There is no Celery and no Beat; the
`django_celery_beat` / `django_celery_results` apps are dead (kept only so old
migrations replay).

| Task | Schedule |
|---|---|
| `core.potd.curate_pick_of_day` | `10 0 * * *` |
| `core.potd.sync_results` | `30 0 * * *` |
| `core.crons.complete_matches_cron` | `0 0 * * *` |
| `core.crons.tournament_cron_bracketMaker` | `0 0 * * *` |
| `core.crons.tournament_cron_2_day_reminder` | `0 0 * * *` |
| `core.crons.expire_invites_cron` | `0 0 * * *` |
| `core.crons.season_lifecycle_cron` | `0 0 * * *` |
| `core.crons.reconcile_subscriptions_cron` | `30 0 * * *` |

- **See / trigger them:** `/admin/status/` shows the live schedule, worker
  liveness, and recent jobs — and has a **Run now** button per task.
- **If crons "aren't running":** confirm the **worker service is deployed and
  up**. The web service alone does *not* run them.
- Times follow `PROCRASTINATE_TIMEZONE` (`America/New_York`).

---

## New host / first-deploy checklist

When standing up a fresh environment (or **changing hosting providers**):

1. **Deploy both services** off this image: a **web** service and a **worker**
   service (+ a Postgres database). Without the worker, no crons fire.
2. **Set env vars** on both services:
   - Core: `SECRET_KEY`, `ALLOWED_HOSTS`, `DATABASE_URL`, `DEBUG=False`, `PORT`
   - Stripe: `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`, (optional `STRIPE_API_VERSION`)
   - Pricing: `PLATFORM_COST` (dollars, e.g. `2.99`)
   - Aggregator (if used): `USE_AGGRIGATOR=true` + its connection vars
3. **Deploy the web service.** Migrations, cache table, and `bootstrap_periodic`
   (→ FREE/PRO plans priced from `PLATFORM_COST`, today's POTD) run
   automatically. *Set `STRIPE_SECRET_KEY` **before** this so PRO gets a Stripe
   `price_id`; if you forgot, redeploy or run `seed_billing_plans` again.*
4. **Stripe webhook (one-time):** open `/admin/stripe-setup/` → create the
   webhook endpoint (points at `/billing/stripe/webhook`) → copy its signing
   secret into `STRIPE_WEBHOOK_SECRET` and redeploy.
5. **Seed sports data (one-time):** `python manage.py seed_sports_leagues`
   (events + Pick of the Day need leagues). Optionally `create_portal_group`.
6. **Aggregator backfill (if you just enabled it):**
   `python manage.py backfill_aggrigator_users`.
7. **Verify:** `/admin/status/` (worker alive, schedule listed), `/pricing/`
   shows the PRO price, and a `Plan` query shows PRO with a non-empty
   `stripe_price_id`.

### When you change `PLATFORM_COST` later
Either redeploy (the entrypoint's `bootstrap_periodic` reconciles the price) or
run `python manage.py sync_platform_cost` immediately. Both mint a new Stripe
Price and keep existing subscriptions on the old one.
