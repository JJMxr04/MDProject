from django.core.paginator import Paginator
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.user.models import User
from core.user.serializers import WriterSerializer
from django.views.decorators.http import require_POST
from core.blog.client.models import Subscription
from django.http import JsonResponse

@login_required(login_url='/auth/login/')
@require_POST
def toggle_subscription(request):
    writer_id = request.POST.get('writer_id')
    is_subscribed = request.POST.get('is_subscribed') == 'true'
    writer = User.objects.get(id=writer_id, is_writer=True)
    
    if is_subscribed:
        request.user.subscribed_writers.add(writer)
        message = "Subscribed to " + writer.username
    else:
        request.user.subscribed_writers.remove(writer)
        message = "Unsubscribed from " + writer.username

    return JsonResponse({'message': message})

@login_required(login_url='/auth/login/')
def writer_list(request):
    # Get the search query and subscribed filter
    query = request.GET.get('search', '')
    subscribed_only = request.GET.get('subscribed_only', 'false').lower() == 'true'
    
    # Get the user's subscriptions if needed
    if subscribed_only:
        subscribed_writers = Subscription.objects.active_subscriptions(user=request.user).values_list('writer_id', flat=True)
        if query:
            writers = User.objects.filter(is_writer=True, id__in=subscribed_writers, username__icontains=query)
        else:
            writers = User.objects.filter(is_writer=True, id__in=subscribed_writers)
    else:
        if query:
            writers = User.objects.filter(is_writer=True, username__icontains=query)
        else:
            writers = User.objects.filter(is_writer=True)
    
    # Pagination
    paginator = Paginator(writers, 5)  # Show 5 writers per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,  # Pass paginated object
        'search_query': query,
        'subscribed_only': subscribed_only,
    }

    return render(request, 'portal/blog/client/client-writer-list.html', context)
