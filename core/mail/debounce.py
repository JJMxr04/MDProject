"""Debounced Procrastinate deferral — at most one queued job per lock key.

The coalescing primitive behind "your opponent made N picks" summaries
and the notification peaks: callers fire it on
every triggering action, but while a job holding the same queueing lock
is still waiting to run, repeat defers are dropped. The one queued job
runs after ``delay_seconds`` and reads current state, so it naturally
covers everything that happened during the window.
"""

from __future__ import annotations

from django.db import transaction
from procrastinate import exceptions as procrastinate_exceptions


def defer_debounced(task, *, lock: str, delay_seconds: int, **task_kwargs) -> bool:
    """Defer ``task`` to run in ``delay_seconds`` unless a job with the
    same queueing ``lock`` is already queued. Returns True if a new job
    was queued, False if an existing one absorbs this call.

    The inner ``atomic()`` is a savepoint: the queueing-lock violation
    surfaces as a DB error, and without the savepoint it would poison a
    caller's open transaction (e.g. ``upload_pick``'s).
    """
    try:
        with transaction.atomic():
            task.configure(
                queueing_lock=lock,
                schedule_in={"seconds": delay_seconds},
            ).defer(**task_kwargs)
        return True
    except procrastinate_exceptions.AlreadyEnqueued:
        return False
