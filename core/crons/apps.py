import logging
import os
import sys

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class CronsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core.crons'
    label = 'core_crons'

    def ready(self):
        # Log a one-shot startup banner listing every registered
        # Procrastinate periodic task. Pairs with the arq-worker boot
        # banner in the aggregator — when an operator pulls Railway logs
        # for the mdproject-worker service, the very first lines should
        # make it obvious WHAT the scheduler thinks it's responsible for.
        #
        # Guarded by ``_should_log_banner()`` so we don't spam every
        # ``manage.py`` invocation (migrations, shell, collectstatic,
        # tests). Only the gunicorn web boot AND the procrastinate worker
        # boot get the banner.
        if not _should_log_banner():
            return
        try:
            self._log_periodic_banner()
        except Exception as exc:  # noqa: BLE001 — never block startup
            logger.warning("crons banner failed: %s: %s",
                           type(exc).__name__, exc)

    def _log_periodic_banner(self):
        is_worker = _is_procrastinate_worker()
        role = "procrastinate-worker" if is_worker else "django-web"

        try:
            from procrastinate.contrib.django import app
            periodic_tasks = list(
                app.periodic_registry.periodic_tasks.values()
            )
        except Exception as exc:  # noqa: BLE001
            periodic_tasks = []
            logger.debug("crons banner: procrastinate not ready: %s", exc)

        lines = [
            "=" * 64,
            f"[{role}] booted — Procrastinate periodic tasks registered:",
        ]
        if not periodic_tasks:
            lines.append("  (no @app.periodic tasks discovered)")
        else:
            for pt in sorted(periodic_tasks, key=lambda p: p.task.name):
                lines.append(
                    f"  - {pt.task.name:<48}  cron={pt.cron}"
                )
        lines.append(
            f"[{role}] cron timezone=UTC (Procrastinate evaluates @app.periodic in UTC)"
        )
        lines.append("=" * 64)
        for line in lines:
            logger.info(line)


def _should_log_banner() -> bool:
    """Only log on the two real long-running boot paths."""
    argv0 = (sys.argv[0] if sys.argv else "").lower()
    argv1 = (sys.argv[1] if len(sys.argv) > 1 else "").lower()
    if "gunicorn" in argv0:
        return True
    # `python manage.py procrastinate worker` — manage.py is argv[0],
    # "procrastinate" is argv[1].
    if "manage.py" in argv0 and argv1 == "procrastinate":
        return True
    return os.environ.get("MDPROJECT_LOG_BANNER") == "1"


def _is_procrastinate_worker() -> bool:
    argv1 = (sys.argv[1] if len(sys.argv) > 1 else "").lower()
    return argv1 == "procrastinate"
