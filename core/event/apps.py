from django.apps import AppConfig
from django.conf import settings


class EventConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core.event'
    label = 'core_event'

    def ready(self):
        if settings.DEBUG:
            from core.crons.scheduler import start_scheduler
            import threading
            scheduler_thread = threading.Thread(target=start_scheduler)
            scheduler_thread.daemon = True
            scheduler_thread.start()
