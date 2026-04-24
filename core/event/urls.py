from django.urls import path
from . import views


app_name = 'core-event'

urlpatterns = [
    path('upcoming-events/', views.upcoming_events_list, name='upcoming-events'),
    path('upcoming-events/<str:event_id>/', views.upcoming_event_detail, name='upcoming-events-detail'),
]
