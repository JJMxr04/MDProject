from django.contrib import admin
from .models import User

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['email', 'username', 'first_name', 'last_name', 'is_staff', 'is_superuser']
    search_fields = ['email', 'username', 'first_name', 'last_name']
    list_filter = ['is_staff', 'is_superuser', 'is_active']
    fieldsets = [
        ('Personal Information', {'fields': ['username', 'email', 'first_name', 'last_name', 'bio', 'avatar']}),
        ('Permissions', {'fields': ['is_staff', 'is_superuser', 'is_active']}),
        ('Important Dates', {'fields': ['created', 'updated']}),
    ]
    readonly_fields = ['created', 'updated']
    ordering = ['-created']

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        # Customize queryset as needed, e.g., prefetch related fields
        return queryset


