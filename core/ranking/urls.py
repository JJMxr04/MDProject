from django.urls import path

from core.ranking import views

# Included under the core-portal namespace (no app_name) — names resolve as
# core-portal:portal-leaderboard.
urlpatterns = [
    path("", views.leaderboard_view, name="portal-leaderboard"),
]
