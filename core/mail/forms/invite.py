from django import forms

from core.mail.models import Invite
from core.user.models import User


class InviteForm(forms.ModelForm):
    class Meta:
        model = Invite
        fields = ['obj_id', 'player', 'sender', 'type', 'accepted', 'invited_date']

    def __init__(self, *args, **kwargs):
        super(InviteForm, self).__init__(*args, **kwargs)
        self.fields['obj_id'].widget.attrs.update({'class': 'form-control'})
        self.fields['player'].widget.attrs.update({'class': 'form-control'})
        self.fields['sender'].widget.attrs.update({'class': 'form-control'})
        self.fields['invited_date'].widget.attrs.update({'class': 'form-control'})
        # Make 'type' field hidden and remove it from widget updates
        self.fields['type'].widget = forms.HiddenInput()

class MatchInviteForm(forms.ModelForm):
    TYPE_CHOICES = [
        ('public', 'Public'),
        ('private', 'Private'),
    ]

    type = forms.ChoiceField(choices=TYPE_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))
    player = forms.ModelChoiceField(queryset=User.objects.all(), required=False, widget=forms.Select(attrs={'class': 'form-control'}))

    class Meta:
        model = Invite
        fields = ['type', 'player']
