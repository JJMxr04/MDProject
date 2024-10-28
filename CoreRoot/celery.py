from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from django.conf import settings
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CoreRoot.settings')

app = Celery('CoreRoot')
app.conf.enable_utc = False

# Configure Celery to use settings defined in Django
app.config_from_object(settings, namespace='CELERY')

# Ensure Celery uses the Django database backend for results
app.loader.override_backends['django-db'] = 'django_celery_results.backends.database:DatabaseBackend'
app.conf.update(
    broker_connection_retry_on_startup=True,  # Retry connecting to the broker on startup
)

# Automatically discover tasks in installed Django apps
app.autodiscover_tasks()

# Configure the Celery beat schedule
app.conf.beat_schedule = {
    'backend_cleanup': {
        'task': 'celery.backend_cleanup',
        'schedule': crontab(minute=0, hour=0, day_of_month=1),  # Runs at midnight on the 1st of every month
        'options': {'expires': 3600}  # Cleanup results after 1 hour
    },
}

# Task to print debug information, helpful for testing if Celery is running correctly
@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
