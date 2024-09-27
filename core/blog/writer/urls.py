from django.urls import path
from . import views


app_name = 'core-blog-writer'

urlpatterns = [
    path('writer-dashboard/', views.writer_dashboard, name='writer-dashboard')
    
]