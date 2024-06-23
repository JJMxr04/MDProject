from django.urls import path
from . import views

app_name = 'core_admin'

urlpatterns = [
    path('dashboard/', views.admin_dashboard, name='admin-dashboard'),
    path('waitlist/', views.waitlist_view, name='admin-waitlist'),
    path('waitlist/approve/<uuid:entry_id>/', views.approve_waitlist_entry, name='approve_waitlist_entry'),
    path('waitlist/mass_approve/', views.mass_approve_waitlist_entries, name='mass_approve_waitlist_entries'),
    path('users/', views.user_list, name='user-list'),
    path('users/<uuid:user_id>/', views.user_detail, name='user-detail'),
    path('tournaments/', views.tournament_list, name='tournament-list'),
    path('tournaments/<uuid:tournament_id>/', views.tournament_detail, name='tournament-detail'),
]
