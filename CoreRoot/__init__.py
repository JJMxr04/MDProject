# Empty — Procrastinate's Django integration (procrastinate.contrib.django)
# discovers its app instance via its own AppConfig.ready(), so no import is
# needed here. The Celery shim that used to live here was removed when
# task processing moved off Redis.
