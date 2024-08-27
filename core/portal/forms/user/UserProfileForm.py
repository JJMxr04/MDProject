from django import forms
from core.user.models import User  # Import your custom User model

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User  # Use the custom User model
        fields = ['username', 'email', 'first_name', 'last_name', 'bio', 'avatar']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This email address is already in use.")
        return email
