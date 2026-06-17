import re

from django import forms
from core.user.models import User
from core.abstract.image_security import validate_image_file, process_image

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class UserProfileForm(forms.ModelForm):
    # Not a model field — sanitized bytes are persisted to UserAvatar (BYTEA)
    # by the view, not onto User. Re-encoded to WEBP via image_security.
    avatar_upload = forms.ImageField(required=False)

    # Declared explicitly (not auto-generated from the model) so they render
    # as native color pickers. Empty allowed → cleaned to None → NULL on User
    # → template/CSS fall back to the standard home(blue)/away(red).
    home_color = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"type": "color"})
    )
    away_color = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"type": "color"})
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'bio',
                  'home_color', 'away_color']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # `bio` is a TextField(null=True) but blank=False, so the ModelForm
        # would otherwise reject an empty bio — which blocks a user with no
        # bio from saving their profile (and thus uploading an avatar).
        self.fields['bio'].required = False

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This email address is already in use.")
        return email

    def _clean_color(self, value):
        value = (value or "").strip()
        if not value:
            return None                      # empty → NULL → CSS default
        if not _HEX_RE.match(value):
            raise forms.ValidationError("Enter a color as #RRGGBB.")
        return value

    def clean_home_color(self):
        return self._clean_color(self.cleaned_data.get('home_color'))

    def clean_away_color(self):
        return self._clean_color(self.cleaned_data.get('away_color'))

    def clean_avatar_upload(self):
        f = self.cleaned_data.get('avatar_upload')
        if not f:
            return None
        validate_image_file(f)          # raises ValidationError on bad input
        return process_image(f).read()  # WEBP bytes
