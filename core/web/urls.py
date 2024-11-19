from django.urls import path, include
from . import views
from core.support.urls.publicUrls import publicurlpatterns as supportUrls
from django.urls import path, include
app_name = 'core-web'

urlpatterns = [
    path('', views.home, name='home'),  # Corrected path
    path('about/', views.about, name='about'),
    path('privacy-policy/', views.privacy_policy, name='private-policy'),
    path('services/', views.services, name='services'),
    path('game-rules/', views.gameRules, name='game-rules'),
    path('contactus/',include(supportUrls))
    
]
