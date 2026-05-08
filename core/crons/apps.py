import logging
import os
import sys

from django.apps import AppConfig
from django.conf import settings

logger = logging.getLogger(__name__)


class CronsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core.crons'
    label = 'core_crons'

    def ready(self):
        # Log a one-shot startup banner listing every registered Celery
        # beat schedule. Pairs with the arq-worker boot banner in the
        # aggregator — when an operator pulls Railway logs for the
        # mdproject-worker service, the very first lines should make
        # it obvious WHAT the scheduler thinks it's responsible for.
        #
        # Guarded by ``_should_log_banner()`` so we don't spam every
        # ``manage.py`` invocation (migrations, shell, collectstatic,
        # tests). Only the gunicorn worker boot AND the celery worker
        # boot get the banner.
        if not _should_log_banner():
            return
        try:
            self._log_beat_banner()
        except Exception as exc:  # noqa: BLE001 — never block startup
            logger.warning("crons banner failed: %s: %s",
                           type(exc).__name__, exc)

    def _log_beat_banner(self):
        schedule = getattr(settings, "CELERY_BEAT_SCHEDULE", {}) or {}
        is_worker = _is_celery_worker()
        role = "celery-worker" if is_worker else "django-web"
        broker = _redacted(getattr(settings, "CELERY_BROKER_URL", ""))

        lines = [
            "=" * 64,
            f"[{role}] booted — Celery beat schedule registered:",
        ]
        if not schedule:
            lines.append("  (no entries in CELERY_BEAT_SCHEDULE)")
        else:
            for name, cfg in sorted(schedule.items()):
                task = cfg.get("task", "?")
                sched = _format_schedule(cfg.get("schedule"))
                lines.append(f"  - {name:<32}  task={task}  when={sched}")
        lines.append(
            f"[{role}] broker={broker}  scheduler={getattr(settings, 'CELERY_BEAT_SCHEDULER', '?')}"
        )
        if is_worker:
            lines.append(
                "[celery-worker] beat is embedded (`celery worker -B`); "
                "do NOT scale this service beyond 1 replica."
            )
        lines.append("=" * 64)
        for line in lines:
            logger.info(line)


def _should_log_banner() -> bool:
    """Only log on the two real long-running boot paths."""
    argv0 = (sys.argv[0] if sys.argv else "").lower()
    if "celery" in argv0:
        return True
    if "gunicorn" in argv0:
        return True
    # Fallback: server-style runs from the entrypoint set this for the
    # web container. Helpful when something is launched via wsgi without
    # the gunicorn binary in argv (rare).
    return os.environ.get("MDPROJECT_LOG_BANNER") == "1"


def _is_celery_worker() -> bool:
    return "celery" in (sys.argv[0] if sys.argv else "").lower()


def _format_schedule(s) -> str:
    """Best-effort one-line summary for a schedule entry."""
    if s is None:
        return "?"
    parts = []
    for attr in ("minute", "hour", "day_of_week", "day_of_month", "month_of_year"):
        val = getattr(s, attr, None)
        if val is None:
            continue
        shown = str(val)
        if shown not in ("*", "0-59", "0-23", "0-6", "1-31", "1-12"):
            parts.append(f"{attr}={shown}")
    return " ".join(parts) if parts else repr(s)


def _redacted(url: str) -> str:
    if not url or "@" not in url or "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    creds, host = rest.split("@", 1)
    user = creds.split(":", 1)[0] if ":" in creds else creds
    return f"{scheme}://{user}:***@{host}"
