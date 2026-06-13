from django.apps import AppConfig


class PotdConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core.potd'
    label = 'core_potd'
    verbose_name = 'Pick of the Day'
