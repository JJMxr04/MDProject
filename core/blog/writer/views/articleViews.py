from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from core.blog.writer.decorator import writer_required, author_required
from core.event.models import Event, Outcome
from core.blog.writer.serializers.article import ArticleSerializer
from core.blog.writer.forms import ArticleForm, UpdateArticleForm
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
@author_required
def update_article(request, art_id):  # Ensure article_id is included
    try:
        article = Article.objects.get(id=art_id,author=request.user)
    except:
        return redirect('core-portal:writer-my-articles')
    form = UpdateArticleForm(instance=article)
    if request.method =='POST':
        form = UpdateArticleForm(request.POST, instance=article)
        if form.is_valid():
            form.save()
            return redirect('core-portal:writer-my-articles')
   
    context = {'UpdateArticleForm':form}
    print(context)

    return render(request,'portal/blog/writer/update-article.html', context)


@login_required(login_url='/auth/login/')
@writer_required
@author_required
def delete_article(request, art_id):  # Ensure article_id is included
    try:
        article = Article.objects.get(id=art_id,author=request.user)
    except:
        return redirect('core-portal:writer-my-articles')
    form = UpdateArticleForm(instance=article)
    if request.method =='POST':
        article.delete()
        return redirect('core-portal:writer-my-articles')
   

    return render(request,'portal/blog/writer/delete-article.html')