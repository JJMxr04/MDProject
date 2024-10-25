from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.blog.writer.models import Article
from core.blog.client.models import Subscription
from django.core.paginator import Paginator 

@login_required(login_url='/auth/login/')
def client_feed(request):
    subscriptions = Subscription.objects.active_subscriptions(user=request.user)
    subscribed_writers = subscriptions.values_list('writer', flat=True)
    articles = Article.objects.filter(author__in=subscribed_writers, is_published=True).order_by('-date_published')

    paginator = Paginator(articles, 5)  # Display 5 articles per page
    page_number = request.GET.get('page')
    articles_page = paginator.get_page(page_number)

    context = {
        'articles': articles_page,
        'is_paginated': articles_page.has_other_pages(),
    }

    return render(request, 'portal/blog/client/client-feed.html', context)
