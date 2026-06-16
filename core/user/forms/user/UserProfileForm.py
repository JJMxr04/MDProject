from django import forms
from core.user.models import User
from core.abstract.image_security import validate_image_file, process_image

class UserProfileForm(forms.ModelForm):
    # Not a model field — sanitized bytes are persisted to UserAvatar (BYTEA)
    # by the view, not onto User. Re-encoded to WEBP via image_security.
    avatar_upload = forms.ImageField(required=False)

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'bio']

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

    def clean_avatar_upload(self):
        f = self.cleaned_data.get('avatar_upload')
        if not f:
            return None
        validate_image_file(f)          # raises ValidationError on bad input
        return process_image(f).read()  # WEBP bytes
