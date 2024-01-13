from rest_framework import routers
from core.game.viewsets.game import GameViewSet



router = routers.SimpleRouter()

router.register(r'game', GameViewSet, basename='game')

urlpatterns = [
    *router.urls,
]