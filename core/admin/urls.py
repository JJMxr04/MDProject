from django.contrib import admin
from django.urls import path, include
from core.admin.admin import custom_admin_view

app_name = 'core_admin'

urlpatterns = [
    path('dashboard/', custom_admin_view, name='custom_dashboard'),
]
