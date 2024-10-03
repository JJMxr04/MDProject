from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.blog.writer.decorator import writer_required
from core.event.models import Event, Outcome
from core.blog.writer.serializers.article import ArticleSerializer
from core.blog.writer.forms import ArticleForm
from core.blog.writer.models import Article
from django.http import HttpResponse, HttpResponseBadRequest

@login_required(login_url='/auth/login/')
@writer_required
def my_articles(request):
    current_user = request.user.id
    # Order articles by date_created in descending order
    articles = Article.objects.filter(author=current_user).order_by('-date_created')
    article = ArticleSerializer(articles, many=True).data
    content = {'articles': articles}
    return render(request, 'portal/blog/writer/my-articles.html', content)

@login_required(login_url='/auth/login/')
@writer_required
def update_article(request,art_id):
    pass