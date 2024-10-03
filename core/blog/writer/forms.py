from .models import Article, Tag
from django.forms import ModelForm, TextInput

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

