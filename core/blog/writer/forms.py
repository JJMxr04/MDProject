from .models import Article, Tag
from django.forms import ModelForm

class ArticleForm(ModelForm):

    class Meta:
        model = Article
        fields = ['title',  'content', 'tags','is_premium',]