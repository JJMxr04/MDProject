from rest_framework import routers
from django.urls import path, include
from core.user.viewsets import UserViewSet
from core.auth.viewsets import RegisterViewSet, LoginViewSet, RefreshViewSet, ActivateUserViewSet

router = routers.SimpleRouter()

# # ##################################################################### #
# # ################### AUTH                       ###################### #
# # ##################################################################### #
#
router.register(r'auth/register', RegisterViewSet, basename='auth-register')
router.register(r'auth/login', LoginViewSet, basename='auth-login')
router.register(r'auth/refresh', RefreshViewSet, basename='auth-refresh')
router.register(r'activate', ActivateUserViewSet, basename='activate')


# ##################################################################### #
# ################### USER                       ###################### #
# ##################################################################### #

router.register(r'user', UserViewSet, basename='user')

urlpatterns = [
    *router.urls,
    path('', include(('core.event.routers', 'core'), namespace="core-api-event")),
    path('activate/<str:token>/', ActivateUserViewSet.as_view({'get': 'retrieve'}), name='activate'),
]