from rest_framework import routers
from core.event.viewsets.event import EventViewSet
from core.event.viewsets.sport import SportViewSet


router = routers.SimpleRouter()

router.register(r'event', EventViewSet, basename='event')
router.register(r'sport', SportViewSet, basename='sport')

urlpatterns = [
    *router.urls,
]