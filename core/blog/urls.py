from django.urls import path, include
from . import views

from .writer.urls import urlpatterns as writerUrls
from .client.urls import urlpatterns as clientUrls


app_name = 'core-blog'

urlpatterns = [
    path('writer/', include(writerUrls)),
    path('client/', include(clientUrls))
    
]
