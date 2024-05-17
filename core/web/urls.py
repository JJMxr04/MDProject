from django.urls import path
from . import views
app_name = 'core-web'

urlpatterns = [
    path('', views.home, name='home'),  # Corrected path
    path('about/', views.about, name='about'),
]
