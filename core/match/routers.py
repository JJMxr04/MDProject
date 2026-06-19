from rest_framework import routers

from core.match.viewsets.match import MatchViewSet, MyMatchViewSet

router = routers.SimpleRouter()

router.register(r'match', MatchViewSet, basename='match')
router.register(r'me/match', MyMatchViewSet, basename='my_match')
urlpatterns = [
    *router.urls,
]
