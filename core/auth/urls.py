from django.urls import path
from . import views
app_name = 'core-auth'

urlpatterns = [
    path('login/', views.login, name='login'),  # Corrected path
]
