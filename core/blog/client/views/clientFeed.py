from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from core.blog.writer.models import Article
from core.blog.client.models import Subscription

@login_required(login_url='/auth/login/')
def client_feed(request):
    # Get all active subscriptions of the current user
    subscriptions = Subscription.objects.active_subscriptions(user=request.user)
    
    # Extract all the writers (authors) the user is subscribed to
    subscribed_writers = subscriptions.values_list('writer', flat=True)
    
    # Get all articles from those writers, ordered by date_published
    articles = Article.objects.filter(author__in=subscribed_writers, is_published=True).order_by('-date_published')
    
    # Paginate articles, 10 per page
    paginator = Paginator(articles, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Check if the request is for loading more articles (AJAX)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # Render only the articles list as JSON
        article_list_html = render(request, 'portal/blog/client/partials/article_list.html', {'articles': page_obj}).content.decode('utf-8')
        return JsonResponse({'html': article_list_html, 'has_next': page_obj.has_next()})
    
    # Pass the paginated articles to the template context
    context = {
        'articles': page_obj,
    }
    return render(request, 'portal/blog/client/client-feed.html', context)
