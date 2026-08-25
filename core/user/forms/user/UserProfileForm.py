import re

from django import forms

from core import timeprefs
from core.abstract.image_security import process_image, validate_image_file
from core.timeprefs import timezone_choices
from core.user.models import User

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class UserProfileForm(forms.ModelForm):
    # Not a model field — sanitized bytes are persisted to UserAvatar (BYTEA)
    # by the view, not onto User. Re-encoded to WEBP via image_security.
    avatar_upload = forms.ImageField(required=False)

    # CharField (not ChoiceField) + Select widget so an out-of-list value
    # normalizes to UTC in clean_timezone instead of erroring (Security M4).
    timezone = forms.CharField(
        required=False,
        label="Timezone",
        widget=forms.Select(),
    )

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
        # clock_format comes from the model (choices-constrained → safe
        # Select). timezone is the declared CharField above.
        fields = ['username', 'email', 'first_name', 'last_name', 'bio',
                  'home_color', 'away_color', 'timezone', 'clock_format']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # `bio` is a TextField(null=True) but blank=False, so the ModelForm
        # would otherwise reject an empty bio — which blocks a user with no
        # bio from saving their profile (and thus uploading an avatar).
        self.fields['bio'].required = False
        # Lazily-built, cached IANA list (common zones first).
        self.fields['timezone'].widget.choices = timezone_choices()
        # Both time prefs are optional: a profile POST that omits them (legacy
        # callers, avatar-only saves) must not wipe the user's stored prefs.
        self.fields['clock_format'].required = False

    def clean_timezone(self):
        # Present → allowlist-validate (bogus → UTC);
        # omitted → keep the user's current zone.
        value = self.cleaned_data.get('timezone')
        if not value:
            return getattr(self.instance, 'timezone', None) or timeprefs.DEFAULT_TIMEZONE
        return timeprefs.normalize_timezone(value)

    def clean_clock_format(self):
        value = self.cleaned_data.get('clock_format')
        if not value:
            return getattr(self.instance, 'clock_format', None) or timeprefs.DEFAULT_CLOCK_FORMAT
        return timeprefs.normalize_clock_format(value)

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
