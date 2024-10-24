from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from core.blog.writer.models import Article
from core.blog.client.models import Subscription

@login_required(login_url='/auth/login/')
def client_feed(request):
    subscriptions = Subscription.objects.active_subscriptions(user=request.user)
    subscribed_writers = subscriptions.values_list('writer', flat=True)
    
    articles = Article.objects.filter(author__in=subscribed_writers, is_published=True).order_by('-date_published')
    
    paginator = Paginator(articles, 10)  # 10 articles per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    articles_data = [
        {
            'title': article.title,
            'writer': {
                'username': article.author.username,
                'avatar': article.author.avatar.url if article.author.avatar else '/static/images/default-avatar.png'
            },
            'date_published': article.date_published.strftime('%Y-%m-%d'),
            'content': article.content[:200] + '...',  # Show a snippet
            'event': article.event.name if article.event else 'N/A',
            'market_key': article.outcome.market.key if article.outcome else 'N/A',
            'outcome_name': article.outcome.name if article.outcome else 'N/A',
            'outcome_price': article.outcome.price if article.outcome else 'N/A',
            'outcome_point': article.outcome.point if article.outcome else 'N/A',
        } for article in page_obj
    ]

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'articles': articles_data,
            'has_next': page_obj.has_next(),
        })

    context = {
        'articles_data': articles_data,  # Pass initial articles data
        'has_next': page_obj.has_next(),
    }
    return render(request, 'portal/blog/client/client-feed.html', context)
