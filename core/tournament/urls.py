from . import views
from django.urls import path, include

app_name = 'core-portal'

urlpatterns = [

    path('me/', views.my_tournaments, name='portal-my-tournaments'),
    path('<uuid:tournament_id>/', views.my_tournament_detail, name='portal-my-tournament-detail'),
    path('round/<uuid:round_id>/', views.my_round_detail_view, name='portal-my-tournament-round-detail'),
]
