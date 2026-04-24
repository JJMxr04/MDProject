from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import User


_AVATAR_STYLE = (
    "display:inline-flex;align-items:center;justify-content:center;"
    "width:36px;height:36px;border-radius:50%;overflow:hidden;"
    "background:#EEF2F7;color:#275d81;font-weight:600;"
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    model = User

    list_display = ['avatar_image', 'email', 'username', 'first_name', 'last_name',
                    'last_login', 'is_staff', 'is_admin', 'activated_link']
    search_fields = ['email', 'username', 'first_name', 'last_name']

    list_filter = ['is_staff', 'is_admin', 'is_active', 'activated_link', 'groups']
    ordering = ['-created']

    fieldsets = (
        (None, {'fields': ['username', 'password']}),
        ('Personal Information', {'fields': ['email', 'first_name', 'last_name', 'bio', 'avatar']}),
        ('Permissions', {'fields': ['activated_link', 'is_staff', 'is_admin', 'is_active', 'is_superuser', 'groups', 'user_permissions']}),
        ('Important Dates', {'fields': ['last_login', 'created', 'updated']}),
    )
    # Django's BaseUserAdmin wires password as a ReadOnlyPasswordHashField with
    # a "change this user's password" link via the url_for_result. Keep the
    # change-password URL available on the list page too.
    readonly_fields = ['created', 'updated', 'is_superuser', 'is_active', 'last_login']

    @admin.display(description='Avatar')
    def avatar_image(self, obj):
        if obj.avatar:
            return format_html(
                '<img src="{}" style="width:36px;height:36px;border-radius:50%;object-fit:cover;" alt="" />',
                obj.avatar.url,
            )
        initial = (obj.first_name or obj.username or '?')[:1].upper()
        return format_html('<span style="{}">{}</span>', mark_safe(_AVATAR_STYLE), initial)
