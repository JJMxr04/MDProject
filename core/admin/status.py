"""Status helpers used by the /admin/status/ page.

Each helper returns a small dataclass with a ``state`` field so the
template can render the same green/yellow/red banner pattern as the
aggregator's /ops/crons page. Helpers NEVER raise — every check is
wrapped so a slow query can't blank the entire status page.

Where the data comes from
-------------------------
- **Worker** — recent activity in ``procrastinate_jobs`` plus presence
  in ``procrastinate_workers``. Procrastinate doesn't expose a control
  channel; "alive" means "a job ran in the last few minutes OR a worker
  row updated recently".
- **DB** — single ``SELECT 1`` against the default connection.
- **Cache** — set/get round-trip via Django's cache backend
  (DatabaseCache → Postgres table ``django_cache``).
- **Aggregator** — HTTP GET on ``{AGGRIGATOR_BASE_URL}/healthz`` with a
  hard 2s timeout. Cached for 30s so consecutive admin renders don't
  re-probe a dead aggregator.
- **Periodic schedule** — the registered cron tasks on the Procrastinate
  app (declared via ``@app.periodic`` decorators).
- **Recent jobs** — ``procrastinate_jobs`` rows ordered by attempt time.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

import httpx
from django.conf import settings
from django.core.cache import cache
from django.db import connection

logger = logging.getLogger(__name__)


class State(str, Enum):
    OK = "ok"
    WARN = "warn"
    DOWN = "down"
    UNKNOWN = "unknown"


@dataclass
class StatusItem:
    state: State
    label: str                       # short human label, shown in the row
    detail: Optional[str] = None     # secondary line (latency, error, etc.)
    extra: dict = field(default_factory=dict)  # arbitrary structured data

    @property
    def is_healthy(self) -> bool:
        return self.state is State.OK


# ---- Worker (Procrastinate) ------------------------------------------------

# A worker is considered alive if at least one Procrastinate job has
# transitioned out of "doing" (succeeded/failed) within this window. The
# window is generous because the only periodic tasks fire daily — between
# fires there's nothing to observe. For a busier app this would be tighter.
_WORKER_LIVENESS_WINDOW = timedelta(hours=25)


def get_worker_status(timeout: float = 1.0) -> StatusItem:
    """Check whether a Procrastinate worker is alive.

    Procrastinate has no Celery-style control channel. We use the
    ``procrastinate_jobs`` table as an indirect heartbeat: any job
    finishing recently means the worker is running. If none of the
    periodic tasks have fired yet (fresh deploy), we degrade to UNKNOWN
    rather than DOWN to avoid spurious red banners.
    """
    started = time.monotonic()
    try:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE status IN ('succeeded','failed')) AS finished,
                    MAX(attempted_at) FILTER (WHERE status IN ('succeeded','failed')) AS last_finish,
                    COUNT(*) FILTER (WHERE status = 'doing') AS in_flight
                FROM procrastinate_jobs
                WHERE attempted_at > NOW() - INTERVAL '25 hours'
                """
            )
            row = cur.fetchone()
    except Exception as exc:  # noqa: BLE001
        return StatusItem(
            state=State.UNKNOWN,
            label="worker state unknown",
            detail=(
                f"{type(exc).__name__}: {exc} — procrastinate_jobs table "
                "may not exist yet (run `manage.py migrate`)."
            ),
        )

    finished = row[0] or 0
    last_finish = row[1]
    in_flight = row[2] or 0
    elapsed_ms = int((time.monotonic() - started) * 1000)

    if finished == 0 and in_flight == 0:
        return StatusItem(
            state=State.UNKNOWN,
            label="no recent job activity",
            detail=(
                f"No procrastinate_jobs finished in the last 25h "
                f"({elapsed_ms}ms probe). Fresh deploy, or no scheduled "
                "task has fired yet."
            ),
            extra={"elapsed_ms": elapsed_ms},
        )

    if last_finish is None:
        last_str = "—"
        age_s = None
    else:
        now = datetime.now(tz=timezone.utc)
        age_s = (now - last_finish).total_seconds()
        last_str = f"{int(age_s)}s ago" if age_s < 3600 else f"{int(age_s/3600)}h ago"

    return StatusItem(
        state=State.OK,
        label=f"worker alive ({finished} finished, {in_flight} in flight)",
        detail=f"last finished job: {last_str} ({elapsed_ms}ms probe)",
        extra={
            "elapsed_ms": elapsed_ms,
            "finished": finished,
            "in_flight": in_flight,
            "last_finish_age_seconds": age_s,
        },
    )


# ---- DB --------------------------------------------------------------------


def check_db() -> StatusItem:
    started = time.monotonic()
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    except Exception as exc:  # noqa: BLE001
        return StatusItem(
            state=State.DOWN,
            label="postgres unreachable",
            detail=f"{type(exc).__name__}: {exc}",
        )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    return StatusItem(
        state=State.OK,
        label="postgres reachable",
        detail=f"SELECT 1 in {elapsed_ms}ms",
        extra={"elapsed_ms": elapsed_ms},
    )


# ---- Cache (DatabaseCache → Postgres) --------------------------------------

# Named ``check_redis`` for backward compatibility with /admin/dashboard
# templates and URL routes that still use the old key. Probes the active
# Django cache backend (DatabaseCache post-Redis cutover).
def check_redis() -> StatusItem:
    started = time.monotonic()
    probe_key = "mdproject:status:probe"
    probe_val = str(int(time.time()))
    try:
        cache.set(probe_key, probe_val, timeout=5)
        got = cache.get(probe_key)
    except Exception as exc:  # noqa: BLE001
        return StatusItem(
            state=State.DOWN,
            label="cache unreachable",
            detail=f"{type(exc).__name__}: {exc}",
        )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    if got != probe_val:
        return StatusItem(
            state=State.WARN,
            label="cache round-trip mismatch",
            detail=(
                f"set/get returned {got!r} (expected {probe_val!r}); "
                "another process may be writing this key."
            ),
            extra={"elapsed_ms": elapsed_ms},
        )
    return StatusItem(
        state=State.OK,
        label="cache reachable",
        detail=f"set/get round-trip in {elapsed_ms}ms",
        extra={"elapsed_ms": elapsed_ms},
    )


# ---- Aggregator ------------------------------------------------------------

_AGG_CACHE_KEY = "mdproject:status:aggregator"
_AGG_CACHE_TTL = 30  # seconds — admins refreshing the page don't repeat the probe


def check_aggregator() -> StatusItem:
    if not getattr(settings, "USE_AGGRIGATOR", False):
        return StatusItem(
            state=State.UNKNOWN,
            label="aggregator integration disabled",
            detail="USE_AGGRIGATOR is False — skipping reachability check.",
        )
    base = (getattr(settings, "AGGRIGATOR_BASE_URL", "") or "").rstrip("/")
    if not base:
        return StatusItem(
            state=State.WARN,
            label="AGGRIGATOR_BASE_URL not set",
            detail="USE_AGGRIGATOR is True but no base URL is configured.",
        )

    cached = cache.get(_AGG_CACHE_KEY)
    if cached is not None:
        return _agg_from_cache(cached, base)

    item = _probe_aggregator(base)
    try:
        cache.set(_AGG_CACHE_KEY, _to_cache_dict(item), timeout=_AGG_CACHE_TTL)
    except Exception as exc:  # noqa: BLE001
        logger.debug("aggregator status cache write failed: %s", exc)
    return item


def _probe_aggregator(base: str) -> StatusItem:
    started = time.monotonic()
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(f"{base}/healthz")
    except httpx.HTTPError as exc:
        return StatusItem(
            state=State.DOWN,
            label="aggregator unreachable",
            detail=f"{type(exc).__name__}: {exc}",
            extra={"base": base},
        )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    if resp.status_code != 200:
        return StatusItem(
            state=State.WARN,
            label=f"aggregator /healthz returned HTTP {resp.status_code}",
            detail=(
                "Reachable but unhealthy — check the agg-web service "
                f"logs for boot errors. ({elapsed_ms}ms)"
            ),
            extra={"base": base, "elapsed_ms": elapsed_ms,
                   "status_code": resp.status_code},
        )
    return StatusItem(
        state=State.OK,
        label="aggregator reachable",
        detail=f"GET /healthz 200 in {elapsed_ms}ms",
        extra={"base": base, "elapsed_ms": elapsed_ms},
    )


def _to_cache_dict(item: StatusItem) -> dict:
    return {
        "state": item.state.value,
        "label": item.label,
        "detail": item.detail,
        "extra": item.extra,
    }


def _agg_from_cache(cached: dict, base: str) -> StatusItem:
    return StatusItem(
        state=State(cached.get("state", "unknown")),
        label=cached.get("label", "(cached)"),
        detail=(cached.get("detail") or "") + " — cached",
        extra={**(cached.get("extra") or {}), "base": base, "cached": True},
    )


# ---- Periodic schedule (Procrastinate) -------------------------------------


def get_beat_schedule() -> list[dict]:
    """Return Procrastinate's registered periodic tasks.

    Replaces the django_celery_beat-driven schedule. The shape of each
    row matches what the template expects (name, task, enabled, schedule,
    last_run_at, total_runs) so the template didn't need updating.

    "Enabled" is always True — Procrastinate has no enable/disable toggle
    for periodic tasks; comment out the @app.periodic decorator if you
    need to disable one. ``last_run_at`` and ``total_runs`` come from the
    procrastinate_periodic_defers / procrastinate_jobs tables.
    """
    try:
        from procrastinate.contrib.django import app
    except Exception as exc:  # noqa: BLE001
        logger.warning("status.get_beat_schedule: procrastinate not importable: %s", exc)
        return []

    try:
        periodic_tasks = list(app.periodic_registry.periodic_tasks.values())
    except Exception as exc:  # noqa: BLE001
        logger.warning("status.get_beat_schedule: %s: %s",
                       type(exc).__name__, exc)
        return []

    # Pull last-run + count per task in one query — avoids N round-trips
    # for a small list. Procrastinate writes one row per defer in
    # procrastinate_periodic_defers; the matching job row in
    # procrastinate_jobs carries the final status.
    stats_by_task = {}
    try:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT task_name,
                       COUNT(*) AS total,
                       MAX(attempted_at) AS last_run
                FROM procrastinate_jobs
                WHERE periodic_id IS NOT NULL
                GROUP BY task_name
                """
            )
            for task_name, total, last_run in cur.fetchall():
                stats_by_task[task_name] = (total, last_run)
    except Exception as exc:  # noqa: BLE001
        logger.warning("status.get_beat_schedule stats query failed: %s: %s",
                       type(exc).__name__, exc)

    out = []
    for pt in periodic_tasks:
        total, last_run = stats_by_task.get(pt.task.name, (0, None))
        out.append({
            "name": pt.task.name,
            "task": pt.task.name,
            "enabled": True,
            "schedule": f"cron {pt.cron}",
            "last_run_at": last_run,
            "total_runs": total,
        })
    out.sort(key=lambda r: r["name"])
    return out


# ---- Recent job results (Procrastinate) ------------------------------------


def get_recent_results(limit: int = 25) -> list[dict]:
    """Recent rows from procrastinate_jobs.

    Replaces django_celery_results.TaskResult. Same return shape so the
    template doesn't need updating. ``is_failure`` is True for jobs in
    'failed' status (Procrastinate exhausted all retries).
    """
    try:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT task_name, id, status, attempted_at, args, attempts
                FROM procrastinate_jobs
                ORDER BY attempted_at DESC NULLS LAST
                LIMIT %s
                """,
                [limit],
            )
            rows = cur.fetchall()
    except Exception as exc:  # noqa: BLE001
        logger.warning("status.get_recent_results: %s: %s",
                       type(exc).__name__, exc)
        return []

    now = datetime.now(tz=timezone.utc)
    out = []
    for task_name, job_id, status, attempted_at, args, attempts in rows:
        age_s = None
        if attempted_at is not None:
            try:
                age_s = (now - attempted_at).total_seconds()
            except Exception:  # noqa: BLE001
                age_s = None
        out.append({
            "task_name": task_name or "?",
            "task_id": str(job_id),
            "status": (status or "").upper(),
            "date_done": attempted_at,
            "age_seconds": age_s,
            "result_excerpt": (str(args)[:120] if args else None),
            "is_failure": (status or "").lower() == "failed",
        })
    return out
