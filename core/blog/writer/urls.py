from django.urls import path
from . import views


app_name = 'core-blog-writer'

urlpatterns = [
    path('writer-dashboard/', views.writer_dashboard, name='writer-dashboard'),
    path('create-article/', views.create_article, name='writer-create-article'),
    path('events/', views.writer_events, name='writer-events'),
    path('events/<str:event_id>', views.writer_event_BMO, name='writer-event-BMO'),
    path('my-articles/', views.my_articles, name='writer-my-articles'),
    path('update-article/<str:art_id>', views.update_article, name='writer-update-article'),
    path('delete-article/<str:art_id>', views.delete_article, name='writer-delete-article')
    
]