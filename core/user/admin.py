
# Admin registration
from django.utils.html import format_html
from django.contrib import admin
from django import forms
from django.contrib.auth.hashers import make_password, check_password
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

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        # Customize queryset as needed, e.g., prefetch related fields
        return queryset

    def avatar_image(self, obj):
        if obj.avatar:
            return format_html('<img src="{}" style="width: 45px; height: 45px;" />', obj.avatar.url)
        return format_html('<img src="/path/to/default/avatar.png" style="width: 45px; height: 45px;" />')

    avatar_image.short_description = 'Avatar'
