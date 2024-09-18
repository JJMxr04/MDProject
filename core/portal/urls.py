from django.urls import path, include, re_path
from . import views
from .views import UserProfileUpdateView
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from core.event.urls import urlpatterns as eventUrls
from core.match.urls import urlpatterns as matchUrls
from core.tournament.urls import urlpatterns as tournamentUrls

app_name = 'core-portal'

urlpatterns = [
    path('dashboard/', views.portal_dashboard, name='portal-dashboard'),
    path('event/', include(eventUrls)), # Ensure this line is correct
    path('match/', include(matchUrls)),
    path('tournament/', include(tournamentUrls)),
    path('profile/', UserProfileUpdateView.as_view(), name='profile'),
]
