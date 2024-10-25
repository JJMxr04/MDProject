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
        articles = paginator.page(1)
    except EmptyPage:
        articles = paginator.page(paginator.num_pages)
    
    # Pass the paginated articles to the template context
    context = {
        'articles': articles,
        'is_paginated': articles.has_other_pages()  # To show the "Load More" button
    }

    return render(request, 'portal/blog/client/client-feed.html', context)
