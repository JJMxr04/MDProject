from django.apps import AppConfig


class MetricsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core.metrics'
    label = 'core_metrics'

    def ready(self):
        # Importing for the user_logged_in receiver registration side-effect
        # (daily-deduped session_start events).
        from core.metrics import signals  # noqa: F401
