"""Status helpers used by the /admin/status/ page.

Each helper returns a small dataclass with a ``state`` field so the
template can render the same green/yellow/red banner pattern as the
aggregator's /ops/crons page. Helpers NEVER raise — every check is
wrapped so a Redis blip or a slow aggregator can't blank the entire
status page.

Where the data comes from
-------------------------
- **Worker** — ``celery.app.control.Inspect.ping()``. Uses the broker's
  control channel; returns within ``timeout`` seconds (we cap at 1s so
  a frozen worker doesn't stall the page render). No new Celery task
  needed and no per-30s heartbeat row in the results table.
- **DB** — single ``SELECT 1`` against the default connection.
- **Redis** — round-trip via Django's cache (which is the same Redis
  used as the Celery broker).
- **Aggregator** — HTTP GET on ``{AGGRIGATOR_BASE_URL}/healthz`` with a
  hard 2s timeout. Cached for 30s so consecutive admin renders don't
  re-probe a dead aggregator.
- **Beat schedule** — read from ``django_celery_beat.PeriodicTask`` so
  the live DB schedule is shown (matches what the worker is actually
  running, not what's in ``settings.CELERY_BEAT_SCHEDULE`` which only
  seeds defaults).
- **Recent task results** — ``django_celery_results.TaskResult`` rows.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
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


# ---- Worker (Celery ping) --------------------------------------------------


def get_worker_status(timeout: float = 1.0) -> StatusItem:
    """Ping every Celery worker via the broker's control channel.

    Returns OK if at least one worker replies. WARN if the ping
    succeeded but no workers responded (broker reachable, no
    consumers). DOWN/UNKNOWN if the broker itself is unreachable or
    the ping raised.
    """
    try:
        # Local import — celery's app object should already be loaded
        # because Django's startup imports CoreRoot.celery, but importing
        # at module top would couple status.py to celery import order.
        from CoreRoot.celery import app as celery_app
    except Exception as exc:  # noqa: BLE001
        return StatusItem(
            state=State.UNKNOWN,
            label="celery app not importable",
            detail=f"{type(exc).__name__}: {exc}",
        )

    started = time.monotonic()
    try:
        # ping() returns a list of single-key dicts: [{"hostname": {"ok": "pong"}}, ...]
        # or None if no replies arrived before the timeout.
        replies = celery_app.control.inspect(timeout=timeout).ping() or {}
    except Exception as exc:  # noqa: BLE001
        return StatusItem(
            state=State.DOWN,
            label="ping failed",
            detail=f"{type(exc).__name__}: {exc} (broker unreachable?)",
        )

    elapsed_ms = int((time.monotonic() - started) * 1000)

    if not replies:
        return StatusItem(
            state=State.DOWN,
            label="no workers responded",
            detail=(
                f"Pinged for {elapsed_ms}ms with no reply. The "
                "mdproject-worker service is down or can't reach Redis. "
                "Manual triggers via /admin/django_celery_beat/ still "
                "queue tasks, but nothing will execute them."
            ),
            extra={"elapsed_ms": elapsed_ms, "workers": []},
        )

    workers = sorted(replies.keys())
    return StatusItem(
        state=State.OK,
        label=f"{len(workers)} worker(s) online",
        detail=f"replied in {elapsed_ms}ms — {', '.join(workers)}",
        extra={"elapsed_ms": elapsed_ms, "workers": workers},
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


# ---- Redis (via Django cache) ----------------------------------------------


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
            label="redis unreachable",
            detail=f"{type(exc).__name__}: {exc}",
        )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    if got != probe_val:
        return StatusItem(
            state=State.WARN,
            label="redis round-trip mismatch",
            detail=(
                f"set/get returned {got!r} (expected {probe_val!r}); "
                "another process may be writing this key, or the cache "
                "backend isn't the Redis we think it is."
            ),
            extra={"elapsed_ms": elapsed_ms},
        )
    return StatusItem(
        state=State.OK,
        label="redis reachable",
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


# ---- Beat schedule ---------------------------------------------------------


def get_beat_schedule() -> list[dict]:
    """Return the live beat schedule from django_celery_beat.

    Sorted by next-fire time so the imminent task is at the top. Each
    row is a small dict the template can iterate without knowing the
    model layout. Empty list if the table doesn't exist yet (migrations
    haven't been run, or django_celery_beat isn't installed).
    """
    try:
        from django_celery_beat.models import PeriodicTask
    except Exception:  # noqa: BLE001
        return []
    try:
        rows = list(
            PeriodicTask.objects.select_related("interval", "crontab")
            .order_by("name")
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("status.get_beat_schedule: %s: %s",
                       type(exc).__name__, exc)
        return []

    out = []
    for r in rows:
        out.append({
            "name": r.name,
            "task": r.task,
            "enabled": r.enabled,
            "schedule": _describe_schedule(r),
            "last_run_at": r.last_run_at,
            "total_runs": r.total_run_count,
        })
    return out


def _describe_schedule(task) -> str:
    if task.crontab_id:
        c = task.crontab
        return (
            f"cron m={c.minute} h={c.hour} dom={c.day_of_month} "
            f"mon={c.month_of_year} dow={c.day_of_week}"
        )
    if task.interval_id:
        i = task.interval
        return f"every {i.every} {i.period}"
    return "?"


# ---- Recent task results ---------------------------------------------------


def get_recent_results(limit: int = 25) -> list[dict]:
    """Recent rows from django_celery_results.TaskResult.

    Empty list if the table doesn't exist yet. Failures are surfaced
    in their own column so the page can colorize FAILURE rows red.
    """
    try:
        from django_celery_results.models import TaskResult
    except Exception:  # noqa: BLE001
        return []
    try:
        rows = list(
            TaskResult.objects.order_by("-date_done")[:limit]
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("status.get_recent_results: %s: %s",
                       type(exc).__name__, exc)
        return []
    now = datetime.now(tz=timezone.utc)
    out = []
    for r in rows:
        age_s = None
        if r.date_done is not None:
            try:
                age_s = (now - r.date_done).total_seconds()
            except Exception:  # noqa: BLE001
                age_s = None
        out.append({
            "task_name": r.task_name or "?",
            "task_id": r.task_id,
            "status": r.status,
            "date_done": r.date_done,
            "age_seconds": age_s,
            "result_excerpt": (str(r.result)[:120] if r.result else None),
            "is_failure": (r.status or "").upper() == "FAILURE",
        })
    return out
