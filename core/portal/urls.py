from django.urls import path, include, re_path
from . import views
from .views import UserProfileUpdateView
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from core.event.urls import urlpatterns as eventUrls
from core.match.urls import urlpatterns as matchUrls

app_name = 'core-portal'

urlpatterns = [
    path('dashboard/', views.portal_dashboard, name='portal-dashboard'),
    path('event/', include(eventUrls)), # Ensure this line is correct
    path('match/', include(matchUrls)),
    path('my/tournaments/', views.my_tournaments, name='portal-my-tournaments'),
    path('my/tournaments/<uuid:tournament_id>/', views.my_tournament_detail, name='portal-my-tournament-detail'),
    path('tournament/round/<uuid:round_id>/', views.my_round_detail_view, name='portal-my-tournament-round-detail'),
    path('profile/', UserProfileUpdateView.as_view(), name='profile'),
]
