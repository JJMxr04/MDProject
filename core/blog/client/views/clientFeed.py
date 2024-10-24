from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.blog.writer.models import Article
from core.blog.client.models import Subscription

@login_required(login_url='/auth/login/')
def client_feed(request):
    # Get all active subscriptions of the current user
    subscriptions = Subscription.objects.active_subscriptions(user=request.user)
    subscribed_writers = subscriptions.values_list('writer', flat=True)

    # Handle pagination
    page = request.GET.get('page', 1)  # Get current page number from the request
    articles_query = Article.objects.filter(author__in=subscribed_writers, is_published=True).order_by('-date_published')
    paginator = Paginator(articles_query, 10)  # Paginate by 10 articles per page

    if request.is_ajax():
        articles_page = paginator.get_page(page)
        articles_data = [
            {
                'title': article.title,
                'writer': {
                    'username': article.writer.username,
                    'avatar_url': article.writer.avatar.url
                },
                'date_created': article.date_created.strftime('%Y-%m-%d'),
                'event': article.event,
                'market': article.outcome.market.key,
                'outcome': {
                    'name': article.outcome.name,
                    'price': article.outcome.price,
                    'point': article.outcome.point,
                },
                'content': article.content
            }
            for article in articles_page
        ]

        return JsonResponse({
            'articles': articles_data,
            'has_next': articles_page.has_next()
        })

    # Initial page load
    context = {
        'articles': paginator.get_page(1)  # Load the first page of articles
    }
    return render(request, 'portal/blog/client/client-feed.html', context)
