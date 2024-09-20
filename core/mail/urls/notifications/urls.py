from rest_framework import routers
from django.urls import path, include
import core.mail.views as views

urlpatterns = [
    path('notifications/',views.get_notifictions, name='get-notifications')
]