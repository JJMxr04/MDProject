from django.contrib import admin
from .models import User

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['email', 'username', 'first_name', 'last_name', 'is_staff', 'is_admin', 'activated_link']
    search_fields = ['email', 'username', 'first_name', 'last_name']
    list_filter = ['is_staff', 'is_admin', 'is_active', 'activated_link']
    fieldsets = [
        ('Personal Information', {'fields': ['username', 'email', 'first_name', 'last_name', 'bio', 'avatar']}),
        ('Permissions', {'fields': ['is_staff', 'is_admin', 'is_active', 'activated_link', 'is_superuser']}),
        ('Important Dates', {'fields': ['created', 'updated']}),
    ]
    readonly_fields = ['created', 'updated', 'is_superuser', 'is_active']
    ordering = ['-created']

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        # Customize queryset as needed, e.g., prefetch related fields
        return queryset
