from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    model = User

    list_display = ['email', 'username', 'first_name', 'last_name',
                    'last_login', 'is_staff', 'is_admin', 'activated_link']
    search_fields = ['email', 'username', 'first_name', 'last_name']

    list_filter = ['is_staff', 'is_admin', 'is_active', 'activated_link', 'groups']
    ordering = ['-created']

    fieldsets = (
        (None, {'fields': ['username', 'password']}),
        ('Personal Information', {'fields': ['email', 'first_name', 'last_name', 'bio']}),
        ('Permissions', {'fields': ['activated_link', 'is_staff', 'is_admin', 'is_active', 'is_superuser', 'groups', 'user_permissions']}),
        ('Important Dates', {'fields': ['last_login', 'created', 'updated']}),
    )
    readonly_fields = ['created', 'updated', 'is_superuser', 'is_active', 'last_login']
