from django.contrib import admin
from django.urls import path, include
from core.admin.admin import custom_admin_view
from core.support.urls import adminUrlPatterns as supportUrlPatterns

app_name = 'core-admin'

urlpatterns = [
    path('dashboard/', custom_admin_view, name='admin_dashboard'),
    path('helpdesk/', include(supportUrlPatterns))
]
