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

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2')

    def clean_email(self):
        email_address = self.cleaned_data.get('email')
        if not WaitlistEntry.objects.filter(email=email_address, admin_granted_access=True).exists():
            raise forms.ValidationError("You have not been approved to register")
        return email_address

    def clean_username(self):
        username = self.cleaned_data.get('username')
        # Add any additional username validation if needed
        return username

    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name')
        # Add any additional first name validation if needed
        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name')
        # Add any additional last name validation if needed
        return last_name

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
            WaitlistEntry.objects.filter(email=user.email).update(activated=True)
            email.send_activation_email(user)
        return user
