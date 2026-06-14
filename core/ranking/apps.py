from django.apps import AppConfig


class RankingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core.ranking"
    label = "core_ranking"

    def ready(self):
        # Progression credit (points/XP/Elo) is called directly from match
        # completion, not via signals. The one signal we wire here gives every
        # new user a PlayerProgress row at signup so the portal always has a
        # level/XP to show.
        from core.ranking import signals  # noqa: F401
