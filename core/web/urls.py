from django.urls import path
from . import views

app_name = 'core-web'

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('privacy-policy/', views.privacy_policy, name='private-policy'),
    path('services/', views.services, name='services'),
    path('game-rules/', views.gameRules, name='game-rules'),
]
