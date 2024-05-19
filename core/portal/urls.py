from django.urls import path
from . import views

app_name = 'core-portal'

urlpatterns = [
    path('dashboard/', views.portal_dashboard, name='portal-dashboard'),  # Corrected path

]
