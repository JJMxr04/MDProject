from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CoreRoot.settings')

app = Celery('CoreRoot')
app.conf.enable_utc = False

# Configure Celery to use settings defined in Django.
# CELERY_BEAT_SCHEDULE in settings.py is the single source of truth for the
# beat schedule. (Earlier this file declared its own ``app.conf.beat_schedule``
# that diverged and pointed at obsolete event/sport tasks; removed as part of
# the aggregator cutover — plan §7.1.)
app.config_from_object(settings, namespace='CELERY')

# Ensure Celery uses the Django database backend for results
app.loader.override_backends['django-db'] = 'django_celery_results.backends.database:DatabaseBackend'
app.conf.update(
    broker_connection_retry_on_startup=True,  # Retry connecting to the broker on startup
)

# Automatically discover tasks in installed Django apps
app.autodiscover_tasks()

# Task to print debug information, helpful for testing if Celery is running correctly
@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
