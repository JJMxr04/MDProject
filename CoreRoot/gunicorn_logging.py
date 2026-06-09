"""Gunicorn access logger that drops container health-probe noise.

Coolify's HEALTHCHECK polls ``/healthz`` every ~10s; without filtering,
every probe lands in the access log and buries real request lines. This
subclass overrides ``access()`` to skip the excluded paths and logs
everything else unchanged. Error logs are untouched.

Wired in via ``gunicorn --logger-class CoreRoot.gunicorn_logging.HealthcheckFilteringLogger``
in ``docker-entrypoint.sh``.
"""

from __future__ import annotations

from gunicorn.glogging import Logger


class HealthcheckFilteringLogger(Logger):
    # ``/readyz`` isn't a route today, but excluding it is free and
    # future-proofs against adding a readiness probe later.
    EXCLUDED_PATHS = frozenset({"/healthz", "/readyz"})

    def access(self, resp, req, environ, request_time):
        if environ.get("PATH_INFO", "") in self.EXCLUDED_PATHS:
            return
        super().access(resp, req, environ, request_time)
