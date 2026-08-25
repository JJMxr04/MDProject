# MDProject

Django app — the user-facing platform. Users pick real sports events against each other in matches and tournaments, chase Pick of the Day streaks, climb seasonal rankings, and can subscribe via Stripe for extra features. It consumes [aggrigator](../aggrigator) as its sole source of live and historical odds/event data over a keyed HTTP API plus inbound webhooks (`USE_AGGRIGATOR=True`) — MDProject never calls odds-api.io or TheSportsDB directly.

## Architecture at a glance

- `core.user`, `core.auth` — accounts, login/register, 2FA (django-otp TOTP + static backup codes), friends
- `core.event` — event/market/odds data mirrored from aggrigator (`core/event/odds/` — SGO taxonomy, normalize)
- `core.game`, `core.match` — the core prediction gameplay: matches between users, each picking real sports events; no-draws resolution
- `core.tournament` — bracket tournaments
- `core.potd` — Pick of the Day + streaks
- `core.ranking` — seasons, ranks, XP/leveling, leaderboards
- `core.billing` — Stripe subscriptions/entitlements
- `core.mail` — transactional email + in-app notifications
- `core.metrics` — in-house product analytics (`ProductEvent` + `track()`)
- `core.portal` — the main authenticated web UI
- `core.api` — JSON API (v1) backing the portal's JS islands
- `core.admin` — custom Django admin config (Jazzmin theme)
- `core.crons` — Procrastinate periodic jobs
- `core.web` — public/marketing pages
- `core.abstract` — shared base utilities (e.g. image-upload security pipeline); a plain Python package, not a Django app
- `CoreRoot/` — Django project settings/urls/wsgi

The task queue is **Procrastinate** (Postgres-backed) via `core.crons`. `celery`, `django-celery-beat`, and `django-celery-results` are still installed dependencies, but they're dead post-cutover — kept only so old migrations replay cleanly on a fresh database. Don't reach for Celery when working on background jobs; it isn't running.

## Local dev setup

```bash
cd MDProject
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env: at minimum set SECRET_KEY, and AGGRIGATOR_SERVICE_KEY once aggrigator
# is running and you've minted a service-tenant key there (see aggrigator's
# scripts/provision_service_tenant.py).
```

MDProject shares the same Homebrew Postgres 18 instance as aggrigator (port 5434, see aggrigator's README for setup) — `.env.example`'s `DATABASE_URL` already points at it with its own `mdproject` database name.

```bash
python manage.py migrate
python manage.py runserver
```

**MDProject needs a running aggrigator instance** for most functionality — events, odds, bets, and analytics all proxy through it. Without `AGGRIGATOR_BASE_URL` pointing at a live aggrigator and a valid `AGGRIGATOR_SERVICE_KEY`, those features will error.

## Running the test suite

```bash
python manage.py test
```

This is Django's built-in test runner, not pytest — there's no `pytest.ini` at the repo root. `event-tests/` is a standalone manual verification script, not part of the automated suite.

## Alternative: Docker

```bash
docker compose up -d
```

This mirrors the Coolify deploy shape (web + Procrastinate worker + postgres + a pre-provisioned-but-unused redis). **Aggrigator is intentionally not included** in this compose file — run it separately and either point `AGGRIGATOR_BASE_URL` at `http://host.docker.internal:8001`, or combine both projects' compose files.

## Deploying

See [`COOLIFY.md`](./COOLIFY.md) (current) or [`RAILWAY.md`](./RAILWAY.md) (legacy) for the full deploy runbooks.
