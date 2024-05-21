from django import forms
from core.auth.models.waitlist import WaitlistEntry

class WaitListForm(forms.ModelForm):
    class Meta:
        model = WaitlistEntry
        fields = ['email', 'full_name']
