from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.urls import path
from .views import custom_logout_view

app_name = 'core_admin'  # Use underscores if needed to match app names

urlpatterns = [
    path('dashboard/', views.admin_dashboard, name='admin-dashboard'),
    path('waitlist/', views.waitlist_view, name='admin-waitlist'),
    path('waitlist/approve/<uuid:entry_id>/', views.approve_waitlist_entry, name='approve_waitlist_entry'),
    path('waitlist/mass_approve/', views.mass_approve_waitlist_entries, name='mass_approve_waitlist_entries'),
    path('users/', views.user_list, name='user-list'),
    path('users/<uuid:user_id>/', views.user_detail, name='user-detail'),

    # path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    path('logout/', custom_logout_view, name='custom_logout'),

]
