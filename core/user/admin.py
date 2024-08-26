# Admin registration
from django.utils.html import format_html
from django.contrib import admin
from django import forms
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from django.shortcuts import render
from .models import User

class UserAdminForm(forms.ModelForm):
    portal_password = forms.CharField(widget=forms.PasswordInput, required=False)

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'bio', 'avatar', 'is_staff', 'is_admin', 'is_active', 'activated_link', 'portal_password']

    def save(self, commit=True):
        user = super().save(commit=False)
        if 'portal_password' in self.changed_data:
            user.portal_password = make_password(self.cleaned_data['portal_password'])
        if commit:
            user.save()
        return user

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    form = UserAdminForm
    list_display = ['avatar_image', 'email', 'username', 'first_name', 'last_name', 'is_staff', 'is_admin', 'activated_link']
    search_fields = ['email', 'username', 'first_name', 'last_name']
    list_filter = ['is_staff', 'is_admin', 'is_active', 'activated_link']
    fieldsets = [
        ('Personal Information', {'fields': ['username', 'email', 'first_name', 'last_name', 'bio', 'avatar']}),
        ('Permissions', {'fields': ['is_staff', 'is_admin', 'is_active', 'activated_link']}),
        ('Security', {'fields': ['portal_password']}),
        ('Important Dates', {'fields': ['created', 'updated']}),
    ]
    readonly_fields = ['created', 'updated', 'is_superuser', 'is_active']
    ordering = ['-created']

    actions = ['set_new_password']

    def avatar_image(self, obj):
        if obj.avatar:
            return format_html('<img src="{}" style="width: 45px; height: 45px;" />', obj.avatar.url)
        return format_html('<img src="/path/to/default/avatar.png" style="width: 45px; height: 45px;" />')

    avatar_image.short_description = 'Avatar'

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset

    # Custom action to set a new password for selected users
    def set_new_password(self, request, queryset):
        # Set a fixed new password
        new_password = 'password'
        hashed_password = make_password(new_password)

        # Update the password for each selected user
        for user in queryset:
            user.password = hashed_password
            user.save()

        # Notify the admin that the action was successful
        self.message_user(request, f"Password updated to 'password' for {queryset.count()} users.")

    set_new_password.short_description = 'Set password to "password" for selected users'


