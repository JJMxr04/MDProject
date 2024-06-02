from django.urls import path
from . import views

app_name = 'core_admin'  # Use underscores if needed to match app names

urlpatterns = [
    path('dashboard/', views.admin_dashboard, name='admin-dashboard'),
]
