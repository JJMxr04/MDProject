from django.apps import AppConfig
from django.conf import settings


class EventConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core.event'
    label = 'core_event'


