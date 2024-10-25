from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.list import ListView
from core.blog.writer.models import Article
from core.blog.client.models import Subscription  # Adjust import according to your project's structure

class ClientFeedView(LoginRequiredMixin, ListView):
    model = Article
    paginate_by = 5
    context_object_name = 'articles'
    template_name = 'portal/blog/client/client-feed.html'
    login_url = '/auth/login/'

    def get_queryset(self):
        # Get all active subscriptions of the current user
        subscriptions = Subscription.objects.active_subscriptions(user=self.request.user)
        
        # Extract all the writers (authors) the user is subscribed to
        subscribed_writers = subscriptions.values_list('writer', flat=True)
        
        # Get all articles from those writers, ordered by date_published
        return Article.objects.filter(author__in=subscribed_writers, is_published=True).order_by('-date_published')


# @login_required(login_url='/auth/login/')
# def client_feed(request):
#     # Get all active subscriptions of the current user
#     subscriptions = Subscription.objects.active_subscriptions(user=request.user)
    
#     # Extract all the writers (authors) the user is subscribed to
#     subscribed_writers = subscriptions.values_list('writer', flat=True)
    
#     # Get all articles from those writers, ordered by date_published
#     articles = Article.objects.filter(author__in=subscribed_writers,is_published=True).order_by('-date_published')
    
#     # Pass the articles to the template context
#     context = {
#         'articles': articles
#     }

#     return render(request, 'portal/blog/client/client-feed.html', context)
