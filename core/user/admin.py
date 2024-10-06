from django.utils.html import format_html
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django import forms
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from django.shortcuts import render
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # Use UserCreationForm and UserChangeForm to manage user creation and editing
    add_form = UserCreationForm
    form = UserChangeForm
    model = User

    # Custom fields for the admin display
    list_display = ['avatar_image', 'email', 'username', 'first_name', 'last_name', 'last_login', 'is_staff',
                    'is_admin', 'activated_link']
    search_fields = ['email', 'username', 'first_name', 'last_name', '_stripe_account_id']  # Added _stripe_account_id here

    list_filter = ['is_staff', 'is_admin', 'is_active', 'activated_link', 'groups']
    ordering = ['-created']

    # Updated fieldsets configuration to include _stripe_account_id under "Writer"
    fieldsets = (
        ('Personal Information', {'fields': ['username', 'email', 'first_name', 'last_name', 'bio', 'avatar']}),
        ('Writer', {'fields': ['is_writer', 'tags', 'writer_description', '_stripe_account_id']}),  # Added _stripe_account_id here
        ('Permissions', {'fields': ['activated_link', 'is_staff', 'is_admin', 'is_active', 'is_superuser', 'groups', 'user_permissions',
                                    ]}),
        ('Important Dates', {'fields': ['last_login', 'created', 'updated']}),
    )

    # Updated fields shown when creating a new user
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
            'email', 'username', 'password1', 'password2', 'is_staff', 'is_active', 'groups', 'user_permissions')}
         ),
        ('Writer', {
            'classes': ('wide',),
            'fields': ('tags', 'writer_description','_stripe_account_id')}
         ),
    )

    # Fields shown when creating a new user
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
            'email', 'username', 'password1', 'password2', 'is_staff', 'is_active', 'groups', 'user_permissions')}
         ),
    )

    # Fields to be read-only
    readonly_fields = ['created', 'updated', 'is_superuser', 'is_active', 'last_login']

    # Actions for admin interface
    actions = ['set_new_password']

    # Custom method to display avatar image
    def avatar_image(self, obj):
        if obj.avatar:
            return format_html('<img src="{}" style="width: 45px; height: 45px;" />', obj.avatar.url)
        return format_html('<img src="/path/to/default/avatar.png" style="width: 45px; height: 45px;" />')

    avatar_image.short_description = 'Avatar'

    # Custom queryset to include additional logic if needed
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset

    # Custom action to set a new password for selected users
    def set_new_password(self, request, queryset):
        # Custom logic for setting a new password for the selected users
        pass
