from django.urls import path, include
from . import views


app_name = 'core-payments'

urlpatterns = [
    path('account_link/', views.create_account_link, name='create_account_link'),
    path('account/', views.create_account, name='create_account'),
    path('return/<str:connected_account_id>/', views.catch_all, name='return'),
    path('refresh/<str:connected_account_id>/', views.catch_all, name='refresh'),
    path('<path:path>/', views.catch_all, name='catch_all'),
    path('', views.catch_all, name='home'),
    path('onboarding/', views.onboarding_page, name='onboarding'),

    
]
