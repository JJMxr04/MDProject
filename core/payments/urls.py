from django.urls import path, include
from . import views


app_name = 'core-payments'

urlpatterns = [
    path('account_link/', views.create_account_link, name='create_account_link'),
    path('account/', views.create_account, name='create_account'),
    path('return/<str:connected_account_id>/', views.catch_all, name='return'),
    path('refresh/<str:connected_account_id>/', views.catch_all, name='refresh'),
    # path('<path:path>/', views.catch_all, name='catch_all'),
    path('', views.catch_all, name='home'),
    path('onboarding/', views.onboarding_page, name='onboarding'),
    path('create-checkout-session/<str:creator_id>/', views.create_checkout_session, name='create-checkout-session'),
    path('webhook/', views.stripe_webhook, name='stripe-webhook'),
    path('success/', views.successful_payment, name='successful-payment'),
    path('manage-subscriptions/',views.recent_invoices_and_subscriptions, name='manage-subscriptions'),
    path('cancel_subscription/<int:subscription_id>/', views.cancel_subscription, name='cancel_subscription'),
    path('success-cancel-subscription/', views.successful_cancel_subscription, name='successful-cancel-subscription'),
    


    
]
