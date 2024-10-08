# mail/admin.py

from django.contrib import admin
from .models import Notification

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'timestamp',)  # Ensure 'timestamp' is a valid field

    # Add this method if 'timestamp' is not a field in the model
    def timestamp(self, obj):
        return obj.created_at  # Replace 'created_at' with the actual field name if different
    timestamp.short_description = 'Timestamp'  # Optional: set a short description for the admin display

    search_fields = ('message', 'user__username', 'user__email')
    ordering = ('-created_at',)
