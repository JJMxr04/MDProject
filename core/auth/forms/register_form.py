# forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from core.user.models import User  # Import your custom user model
from core.auth.models.waitlist import WaitlistEntry
from core.auth.models import email  # Import your email sending function

class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text='Required. Enter a valid email address.')
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    register_as_writer = forms.BooleanField(required=False, label='Register as a writer', initial=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2', 'register_as_writer')

    def clean_email(self):
        email_address = self.cleaned_data.get('email')
        if not WaitlistEntry.objects.filter(email=email_address, admin_granted_access=True).exists():
            raise forms.ValidationError("You have not been approved to register")
        return email_address

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.is_writer = self.cleaned_data.get('register_as_writer', False)  # Set 'is_writer' field
        if commit:
            user.save()
            WaitlistEntry.objects.filter(email=user.email).update(activated=True)
            email.send_activation_email(user)
        return user
