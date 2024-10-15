# mail/admin.py

from django.contrib import admin
from .models import Invite
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

@admin.register(Invite)
class InviteAdmin(admin.ModelAdmin):
    # Fields to display in the list view
    list_display = ('id', 'obj_id', 'player', 'sender', 'type', 'accepted', 'state', 'invited_date', 'accepted_date')
    
    # Filters to allow admins to filter invites by certain fields
    list_filter = ('type', 'accepted', 'state', 'invited_date', 'accepted_date')
    
    # Enable search by related usernames, obj_id, and invite type
    search_fields = ('player__username', 'sender__username', 'obj_id', 'type')
    
    # Fields to be displayed when viewing or editing an individual invite
    fields = ('obj_id', 'player', 'sender', 'type', 'accepted', 'accepted_date', 'invited_date', 'state')
    
    # Read-only fields that cannot be modified from the admin interface
    readonly_fields = ('id', 'accepted_date', 'invited_date')

    # Define how the invites should be ordered (descending by invite date)
    ordering = ('-invited_date',)

    # Custom method to display full player and sender information
    def player_username(self, obj):
        return obj.player.username

    def sender_username(self, obj):
        return obj.sender.username



