from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.blog.writer.decorator import writer_required
from core.event.models import Event, Sport  # Adjust import according to your project's structure
from django.utils.dateparse import parse_date
from core.event.serializers.event import EventSerializer
import json
from uuid import UUID
from django.core.serializers.json import DjangoJSONEncoder
from core.blog.writer.forms import ArticleForm
from django.http import HttpResponse


@login_required(login_url='/auth/login/')
@writer_required
def create_article(request):
    
    form = ArticleForm()
    if request.method == 'POST':
        print(request.POST)
        form = ArticleForm(request.POST)
        if form.is_valid():
            article = form.save(commit=False)
            article.author = request.user
            article.save()
            return HttpResponse('Article created!')
    context = {'CreateArticleForm':form}
    return render(request,'portal/blog/writer/create-article.html', context)