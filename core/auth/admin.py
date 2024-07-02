from django.contrib import admin
from .models.waitlist import WaitlistEntry
from core.mail.models import Emails


class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ('email', 'full_name', 'phone_number', 'registered', 'activated', 'admin_granted_access', 'created', 'updated')
    list_filter = ('registered', 'activated', 'admin_granted_access')
    search_fields = ('email', 'full_name', 'phone_number', 'description')

    actions = ['approve_entries', 'revoke_entries']  # Register both actions

    def approve_entries(self, request, queryset):
        updated_count = 0
        for entry in queryset:
            if not entry.admin_granted_access:
                entry.admin_granted_access = True
                entry.save()
                updated_count += 1
                Emails.send_waitlist_granted(email=entry.email) # Sending an email
        self.message_user(request, f'{updated_count} entry(s) approved successfully.')



    def revoke_entries(self, request, queryset):
        updated_count = 0
        for entry in queryset:
            if entry.admin_granted_access:
                entry.admin_granted_access = False
                entry.save()
                updated_count += 1
        self.message_user(request, f'{updated_count} entry(s) access revoked successfully.')

    approve_entries.short_description = "Approve selected entries"
    revoke_entries.short_description = "Revoke selected entries"

admin.site.register(WaitlistEntry, WaitlistEntryAdmin)
