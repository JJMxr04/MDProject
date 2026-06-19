from rest_framework import routers

from core.admin.viewsets.admin_stats import AdminStatsViewSet
from core.admin.viewsets.waitlist import WaitlistEntryApprovalViewSet, WaitlistEntryViewSet

router = routers.SimpleRouter()

# router.register(r'stats', MatchViewSet, basename='adminStats')
router.register(r'waitlist', WaitlistEntryViewSet, basename='admin-waitlist')
router.register(r'waitlist-approve', WaitlistEntryApprovalViewSet, basename='admin-waitlist-approval')
router.register(r'stats', AdminStatsViewSet, basename='admin-waitlist')
urlpatterns = [
    *router.urls,
]
