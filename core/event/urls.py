from django.urls import path
from . import views


app_name = 'core-event'

urlpatterns = [
    path('upcoming-events/', views.upcoming_events_list, name='upcoming-events'),
    path('upcoming-events/<str:event_id>/', views.upcoming_event_detail, name='upcoming-events-detail'),
    # path('forums/', views.forum_list, name='forum_list'),
    # path('forums/<int:forum_id>/threads/', views.thread_list, name='thread_list'),
    # path('threads/<int:thread_id>/', views.thread_detail, name='thread_detail'),
    # path('forums/<int:forum_id>/threads/create/', views.create_thread, name='create_thread'),
    # path('threads/<int:thread_id>/posts/create/', views.create_post, name='create_post_thread'),
    path('<str:event_id>/posts/create/', views.create_post, name='create_post_event'),
    
]
