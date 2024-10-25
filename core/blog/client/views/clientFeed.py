from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from core.blog.writer.models import Article
from core.blog.client.models import Subscription
from core.event.serializers.event import EventSerializer

@login_required(login_url='/auth/login/')
def client_feed(request):
    # Get all active subscriptions of the current user
    subscriptions = Subscription.objects.active_subscriptions(user=request.user)
    subscribed_writers = subscriptions.values_list('writer', flat=True)
    articles_list = Article.objects.filter(author__in=subscribed_writers, is_published=True).order_by('-date_published')

    # Pagination setup
    page = request.GET.get('page', 1)
    paginator = Paginator(articles_list, 5)

    try:
        articles = paginator.page(page)
        has_more = articles.has_next()
    except PageNotAnInteger:
        articles = paginator.page(1)
        has_more = articles.has_next()
    except EmptyPage:
        articles = []
        has_more = False  # No more articles to paginate

    # Check if the request is an AJAX request
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # Prepare articles data to send as JSON
        articles_data = [
            {
                'title': article.title,
                'content': article.content,
                'writer': {
                    'username': article.author.username,
                    'avatar_url': article.author.avatar.url
                },
                'date_created': article.date_created.strftime('%Y-%m-%d'),
                'event': EventSerializer(article.event).data,
                'market': article.outcome.market.key,
                'outcome': {
                    'name': article.outcome.name,
                    'price': article.outcome.price,
                    'point': article.outcome.point
                }
            }
            for article in articles
        ]

        return JsonResponse({'articles': articles_data, 'has_more': has_more})

    # Render the page for initial load
    context = {
        'articles': articles,
        'is_paginated': hasattr(articles, 'has_other_pages') and articles.has_other_pages(),
        'has_more': has_more,
    }
    return render(request, 'portal/blog/client/client-feed.html', context)
