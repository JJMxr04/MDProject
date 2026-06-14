from django.apps import AppConfig


class RankingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core.ranking"
    label = "core_ranking"

    def ready(self):
        # Engine hooks are called directly from match completion (no signals),
        # so nothing to wire here yet. Kept for symmetry / future signals.
        return None
