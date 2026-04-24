from django.urls import path
from core.admin.admin import custom_admin_view

app_name = 'core-admin'

urlpatterns = [
    path('dashboard/', custom_admin_view, name='admin_dashboard'),
]
