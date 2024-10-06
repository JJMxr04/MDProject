from django.contrib import admin
from .models import Subscription  # Import the Subscription model

class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'writer', 'subscriber', 'start_date', 'end_date')  # Added writer and subscriber
    search_fields = ('subscriber__username','writer__username')  # Enable search by subscriber's username

admin.site.register(Subscription, SubscriptionAdmin)  # Register the Subscription model with the custom admin class
