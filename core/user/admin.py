from django import forms
from django.utils.html import format_html
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

# Custom form to handle stripe_account_id
class UserChangeForm(forms.ModelForm):
    stripe_account_id = forms.CharField(required=False, label="Stripe Account ID")

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'bio', 'avatar', 'is_writer', 'tags', 
                  'writer_description', 'stripe_account_id')

    def save(self, commit=True):
        user = super().save(commit=False)
        # Encrypt the stripe_account_id before saving
        if self.cleaned_data['stripe_account_id']:
            user.stripe_account_id = self.cleaned_data['stripe_account_id']
        if commit:
            user.save()
        return user
    
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserChangeForm
    model = User

    list_display = ['avatar_image', 'email', 'username', 'first_name', 'last_name', 'last_login', 'is_staff',
                    'is_admin', 'activated_link']
    search_fields = ['email', 'username', 'first_name', 'last_name', 'stripe_account_id']  # Search by decrypted stripe_account_id

    list_filter = ['is_staff', 'is_admin', 'is_active', 'activated_link', 'groups']
    ordering = ['-created']

    fieldsets = (
        ('Personal Information', {'fields': ['username', 'email', 'first_name', 'last_name', 'bio', 'avatar']}),
        ('Writer', {'fields': ['is_writer', 'tags', 'writer_description', 'stripe_account_id']}),  # Show decrypted stripe_account_id
        ('Permissions', {'fields': ['activated_link', 'is_staff', 'is_admin', 'is_active', 'is_superuser', 'groups', 'user_permissions']}),
        ('Important Dates', {'fields': ['last_login', 'created', 'updated']}),
    )

    readonly_fields = ['created', 'updated', 'is_superuser', 'is_active', 'last_login']

    def avatar_image(self, obj):
        if obj.avatar:
            return format_html('<img src="{}" style="width: 45px; height: 45px;" />', obj.avatar.url)
        return format_html('<img src="/path/to/default/avatar.png" style="width: 45px; height: 45px;" />')

    avatar_image.short_description = 'Avatar'

    # Override get_fieldsets to ensure stripe_account_id is shown properly
    def get_fieldsets(self, request, obj=None):
        if obj:
            try:
                # Attempt to set the initial value for stripe_account_id
                if obj.stripe_account_id:
                    self.form.base_fields['stripe_account_id'].initial = obj.stripe_account_id
                else:
                    self.form.base_fields['stripe_account_id'].initial = "No value set"
            except Exception as e:
                # Handle possible decryption errors
                self.form.base_fields['stripe_account_id'].initial = "Invalid or corrupted"
                print(f"Decryption error: {e}")
        return super().get_fieldsets(request, obj)