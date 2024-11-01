from django import forms
from core.event.models import Thread, Post
from django.core.exceptions import ValidationError

class ThreadForm(forms.ModelForm):
    class Meta:
        model = Thread
        fields = ['title']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Enter thread title...'}),
        }

class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['content', 'thread', 'event']
        widgets = {
            'content': forms.Textarea(attrs={'placeholder': 'Share your thoughts...'}),
            'thread': forms.HiddenInput(),
            'event': forms.HiddenInput(),
        }

    def clean(self):
        cleaned_data = super().clean()
        thread = cleaned_data.get('thread')
        event = cleaned_data.get('event')

        # Validation to ensure that either 'thread' or 'event' is provided, but not both.
        if not thread and not event:
            raise ValidationError("Please associate this post with either a thread or an event.")
        if thread and event:
            raise ValidationError("A post cannot be associated with both a thread and an event.")
        
        return cleaned_data
