from __future__ import absolute_import, unicode_literals
import os

from celery import Celery
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CoreRoot.settings')

app = Celery('CoreRoot')
app.conf.enable_utc = False

app.config_from_object(settings, namespace='CELERY')

app.autodiscover_tasks()

app.conf.beat_schedule = {
    'backend_cleanup': {
        'task': 'celery.backend_cleanup',
        'schedule': None,
        'result_expires': None
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")