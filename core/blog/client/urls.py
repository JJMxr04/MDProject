from django.urls import path
from . import views


app_name = 'core-blog-client'

urlpatterns = [
    path('client-dashboard/', views.client_dashboard, name='client-dashboard'),
    path('client-feed/', views.client_feed, name='client-feed'),
]