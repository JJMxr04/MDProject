from django.contrib import admin
from .models.waitlist import WaitlistEntry

class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ('email', 'full_name', 'phone_number', 'registered', 'activated', 'admin_granted_access', 'created', 'updated')
    list_filter = ('registered', 'activated', 'admin_granted_access')
    search_fields = ('email', 'full_name', 'phone_number', 'description')

    def approve_entries(self, request, queryset):
        updated_count = queryset.update(admin_granted_access=True)
        self.message_user(request, f'{updated_count} entry(s) approved successfully.')

    approve_entries.short_description = "Approve selected entries"

admin.site.register(WaitlistEntry, WaitlistEntryAdmin)
