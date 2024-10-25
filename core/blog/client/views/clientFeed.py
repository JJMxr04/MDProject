from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.blog.writer.models import Article
from core.blog.client.models import Subscription  # Adjust import according to your project's structure

@login_required(login_url='/auth/login/')
def client_feed(request):
    # Get all active subscriptions of the current user
    subscriptions = Subscription.objects.active_subscriptions(user=request.user)
    
    # Extract all the writers (authors) the user is subscribed to
    subscribed_writers = subscriptions.values_list('writer', flat=True)
    
    # Get all articles from those writers, ordered by date_published
    articles = Article.objects.filter(
        author__in=subscribed_writers,
        is_published=True
    ).order_by('-date_published')
    
    # Paginate the articles, 10 articles per page
    page = request.GET.get('page', 1)
    paginator = Paginator(articles, 10)
    try:
        articles = paginator.page(page)
    except PageNotAnInteger:
        articles = paginator.page(1)
    except EmptyPage:
        articles = paginator.page(paginator.num_pages)
    
    # Determine if there are more articles to load
    is_paginated = articles.has_next()

    # Pass the articles and pagination info to the template context
    context = {
        'articles': articles,
        'is_paginated': is_paginated,
    }

    # Check if the request is an AJAX request
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # If the request is an AJAX request, render only the articles template
        return render(request, 'portal/blog/client/partials/article_list.html', context)

    # For non-AJAX requests, render the full template
    return render(request, 'portal/blog/client/client-feed.html', context)
