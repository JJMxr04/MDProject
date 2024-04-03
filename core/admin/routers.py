from rest_framework import routers

from core.admin.viewsets.waitlist import WaitlistEntryViewSet



router = routers.SimpleRouter()

# router.register(r'stats', MatchViewSet, basename='adminStats')
router.register(r'waitlist', WaitlistEntryViewSet, basename='admin-waitlist')
urlpatterns = [
    *router.urls,
]