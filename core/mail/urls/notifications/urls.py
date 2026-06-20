from django.urls import include, path
from rest_framework import routers

import core.mail.views as views

app_name = 'core-mail'

urlpatterns = [
    path('notifications/',views.get_notifications, name='get-notifications'),
    path('notifications/<uuid:not_id>/', views.read_notifications, name='read_notifications'),
    path('create-invite/', views.create_invite, name='create_invite'),
    path('invite-success/', views.success_invite, name='invite-success'),
    path('invites/', views.invite_list, name='invite-list'),
    path('invite-email/', views.invite_by_email, name='invite-by-email'),
    path('invites/<str:invite_id>', views.accept_invite, name='invite-accept'),
]
