from django.urls import include, path

import core.user.views as views

from .views import UserProfileUpdateView

app_name = 'core-portal'

urlpatterns = [
    path('profile/', UserProfileUpdateView.as_view(), name='profile'),
    path('friends/search/', views.friend_search, name='friend_search'),
    path('friends/add/<uuid:user_id>/', views.add_friend_action, name='add_friend_action'),
    path('friends/regenerate-code/', views.regenerate_friend_code, name='regenerate_friend_code'),
    path('friends/remove/<uuid:friend_id>/', views.remove_friend_action, name='remove_friend_action'),
]
