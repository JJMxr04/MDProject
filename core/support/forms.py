from django import forms
from .models import Ticket, Comment

class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['title', 'description', 'category']

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['message']


# forms.py

class ContactUsForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['email','title', 'description', 'category']
        widgets = {
            'email': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter email'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Describe your issue'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'email': 'Email',
            'title': 'Subject',
            'description': 'Message',
            'category': 'Category'
        }
