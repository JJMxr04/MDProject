from django import forms
from core.auth.models.waitlist import WaitlistEntry

class WaitListForm(forms.ModelForm):
    class Meta:
        model = WaitlistEntry
        fields = ['email', 'full_name']

    def save(self, commit=True):
        # Route through the manager so send_waitlist_thank_you fires.
        # ModelForm.save() would call WaitlistEntry().save() directly and
        # skip the manager's create_entry() — that's why earlier waitlist
        # signups never produced an email.
        cleaned = self.cleaned_data
        return WaitlistEntry.objects.create_entry(
            email=cleaned["email"],
            full_name=cleaned["full_name"],
        )
