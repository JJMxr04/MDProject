# mail/urls.py

from django.urls import include, path
from rest_framework import routers

from .viewsets.notification import NotificationViewSet

router = routers.SimpleRouter()
router.register(r'notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    *router.urls,
]
