from django.urls import path
from . import views


app_name = 'core-blog-client'

urlpatterns = [
    path('client-dashboard/', views.client_dashboard, name='client-dashboard'),
    path('client-feed/', views.client_feed, name='client-feed'),
    path('writer', views.writer_list, name='client-writer-list'),
    path('writer/<str:writer_id>', views.writer_subscribe, name='client-writer-subscribe'),
    path('writers/toggle-subscription/', views.toggle_subscription, name='client-writer-toggle-subscription'),

]