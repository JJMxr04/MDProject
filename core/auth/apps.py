from django.apps import AppConfig


class AuthConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core.auth'
    label = 'core_auth'

    def ready(self):
        # Import for the login-security receiver registration side-effect.
        from core.auth import signals  # noqa: F401
