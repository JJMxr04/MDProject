from django.urls import path,include
from core.support import views


publicurlpatterns = [

    path('', views.contact_us, name='contact-us'),
]