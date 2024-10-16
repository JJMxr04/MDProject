from django.urls import path, include, re_path
from . import views
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from core.admin.admin import custom_admin_view
from core.support.urls import adminUrlPatterns as supportUrlPatterns

app_name = 'core-admin'

urlpatterns = [
    path('dashboard/', custom_admin_view, name='admin_dashboard'),
    path('helpdesk/', include(supportUrlPatterns))
]
