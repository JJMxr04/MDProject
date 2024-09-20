# mail/urls.py

from rest_framework import routers
from django.urls import path, include
from .viewsets.notification import NotificationViewSet

router = routers.SimpleRouter()
router.register(r'notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    *router.urls,
]
