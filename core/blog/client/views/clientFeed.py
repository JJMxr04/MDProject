from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.blog.writer.models import Article
from core.blog.client.models import Subscription

@login_required(login_url='/auth/login/')
def client_feed(request):
    # Get all active subscriptions of the current user
    subscriptions = Subscription.objects.active_subscriptions(user=request.user)

    # Extract all the writers (authors) the user is subscribed to
    subscribed_writers = subscriptions.values_list('writer', flat=True)

    # Get all articles from those writers, ordered by date_published
    articles_list = Article.objects.filter(author__in=subscribed_writers, is_published=True).order_by('-date_published')

    # Set up pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(articles_list, 5)  # Display 5 articles per page

    try:
        articles = paginator.page(page)
    except PageNotAnInteger:
        articles = paginator.page(1)  # Return first page if page is not an integer
    except EmptyPage:
        articles = paginator.page(paginator.num_pages)  # Return last page if page is out of range

    # Check if there are more articles to load
    has_more = articles.has_next()

    # Pass the paginated articles and the has_more flag to the template context
    context = {
        'articles': articles,
        'is_paginated': articles.has_other_pages(),  # This indicates if there are other pages
        'has_more': has_more,  # Indicates if more articles are available
    }

    # Optionally log to see how many articles are being sent
    print(f"Loaded {len(articles)} articles. Has more: {has_more}")

    return render(request, 'portal/blog/client/client-feed.html', context)
