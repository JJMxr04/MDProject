from django.apps import AppConfig


class WriterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core.blog.writer'
    label = 'core_blog_writer'
