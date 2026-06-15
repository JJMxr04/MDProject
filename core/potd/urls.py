from django.urls import path

from core.potd import views

urlpatterns = [
    path('pick/', views.make_pick, name='potd-pick'),
    path('leaderboard/', views.leaderboard, name='potd-leaderboard'),
    path('me/', views.my_picks, name='potd-my-picks'),
]
