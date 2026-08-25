from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core.billing'
    label = 'core_billing'

    def ready(self) -> None:
        # Import signal handlers — the post_save on User that provisions
        # tenant rows in the aggrigator lives in core/billing/signals.py.
        # Imported here for the signal registration side effect.
        from core.billing import signals  # noqa: F401
