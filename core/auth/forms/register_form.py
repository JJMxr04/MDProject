# forms.py
from datetime import date

from django import forms
from django.contrib.auth.forms import UserCreationForm
from core.user.models import User  # Import your custom user model
from core.auth.models.waitlist import WaitlistEntry
from core.auth.models import email  # Import your email sending function

# Paradise Sports is an 18+ only service.
MINIMUM_AGE = 18


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text='Required. Enter a valid email address.')
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    date_of_birth = forms.DateField(
        required=True,
        label='Date of birth',
        help_text='You must be at least 18 years old to register.',
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    age_confirmation = forms.BooleanField(
        required=True,
        label='I confirm that I am 18 years of age or older.',
        error_messages={'required': 'You must confirm that you are 18 or older to register.'},
    )
    # register_as_writer = forms.BooleanField(required=False, label='Register as a writer', initial=False)

    class Meta:
        model = User
        # fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2', 'register_as_writer')
        fields = ('username', 'email', 'first_name', 'last_name', 'date_of_birth', 'password1', 'password2', )

    def clean_email(self):
        email_address = self.cleaned_data.get('email')
        # A live friend invite to this email IS the access grant (plan
        # Phase 4 §3, D-4b) — being asked-for by an existing player
        # bypasses the waitlist. Referral links (?ref=<friend_code>) do
        # NOT bypass it; only explicit email invites do.
        from core.mail.models import PendingInvite
        if PendingInvite.objects.valid_for_email(email_address).exists():
            return email_address
        if not WaitlistEntry.objects.filter(email=email_address, admin_granted_access=True).exists():
            raise forms.ValidationError("You have not been approved to register")
        return email_address

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob is None:
            return dob
        today = date.today()
        if dob > today:
            raise forms.ValidationError("Date of birth cannot be in the future.")
        # Whole years old, accounting for whether the birthday has occurred yet this year.
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age < MINIMUM_AGE:
            raise forms.ValidationError(f"You must be at least {MINIMUM_AGE} years old to register.")
        return dob

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.date_of_birth = self.cleaned_data['date_of_birth']
        # user.is_writer = self.cleaned_data.get('register_as_writer', False)  # Set 'is_writer' field
        if commit:
            user.save()
            WaitlistEntry.objects.filter(email=user.email).update(activated=True)
        return user
