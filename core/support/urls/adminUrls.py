from django.urls import path
from core.support import views

app_name = 'core-support'

urlpatterns = [
    path('tickets/', views.ticket_list, name='ticket_list'),
    path('tickets/new/', views.create_ticket, name='create_ticket'),
    path('tickets/<int:ticket_id>/', views.ticket_detail, name='ticket_detail'),
    path('update_ticket_status/', views.update_ticket_status, name='update_ticket_status'),
    path('update-status-order/', views.update_status_order, name='update_status_order'),
]