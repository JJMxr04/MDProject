from django.urls import path
from . import views
from .views import waitlist_view, approve_waitlist_entry

app_name = 'core_admin'  # Use underscores if needed to match app names

urlpatterns = [
    path('dashboard/', views.admin_dashboard, name='admin-dashboard'),
    path('waitlist/', waitlist_view, name='admin-waitlist'),
    path('waitlist/approve/<uuid:entry_id>/', views.approve_waitlist_entry, name='approve_waitlist_entry'),
    path('waitlist/mass_approve/', views.mass_approve_waitlist_entries, name='mass_approve_waitlist_entries'),

]
