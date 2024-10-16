from rest_framework import routers
from django.urls import path, include
import core.mail.views as views

app_name = 'core-mail'

urlpatterns = [
    path('notifications/',views.get_notifications, name='get-notifications'),
    path('notifications/<uuid:not_id>/', views.read_notifications, name='read_notifications'),
    path('create-invite/', views.create_invite, name='create_invite'),
    path('invite-success/', views.success_invite, name='invite-success'),
    path('invite-accept/<uuid:invite_id>', views.accept_invite, name='invite-accept'),
]