import os
from django.apps import AppConfig
from django.conf import settings

class BlogConfig(AppConfig):
    name = 'core.blog'  # Ensure this matches the full Python path to the app

    def ready(self):
        # Automatically include apps in the 'blog' directory
        blog_apps = os.listdir(os.path.dirname(__file__))
        for app_name in blog_apps:
            app_path = os.path.join(os.path.dirname(__file__), app_name)
            if os.path.isdir(app_path) and app_name not in settings.INSTALLED_APPS and app_name != 'migrations':
                settings.INSTALLED_APPS.append(app_name)
