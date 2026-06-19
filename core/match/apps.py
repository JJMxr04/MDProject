from django.apps import AppConfig


class MatchConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core.match'
    label = 'core_match'

    def ready(self):
        # Importing for the pre_save receiver registration side-effect.
        from core.match import signals  # noqa: F401
