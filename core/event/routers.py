from rest_framework import routers
from core.event.viewsets import EventViewSet, SportViewSet


router = routers.SimpleRouter()

router.register(r'event', EventViewSet, basename='event')
router.register(r'event/sport', SportViewSet, basename='sport')

urlpatterns = [
    *router.urls,
]