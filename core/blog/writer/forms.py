from .models import Article, Tag
from django.forms import ModelForm, TextInput
from django.conf import settings
from django.contrib.auth import get_user_model
# from core.user.models import User
User = get_user_model()

class ArticleForm(ModelForm):

    class Meta:
        model = Article
        fields = ['title',   'content', 'tags','is_premium',]


class UpdateArticleForm(ModelForm):
    class Meta:
        model = Article
        fields = ['title', 'event', 'outcome', 'content', 'tags', 'is_premium']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make 'event' and 'outcome' fields disabled (read-only)
        self.fields['event'].disabled = True
        self.fields['outcome'].disabled = True

class WriterProfileForm(ModelForm):
    password = None

    class Meta:
        model = User
        fields = ['avatar', 'username', 'email', 'first_name', 'last_name', 'writer_descritption', 'tags']
        exclude = ['password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make fields read-only (disabled)
        self.fields['username'].disabled = True
        self.fields['email'].disabled = True
        self.fields['first_name'].disabled = True
        self.fields['last_name'].disabled = True


