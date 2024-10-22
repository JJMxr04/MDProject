from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.user.models import User
from core.user.serializers import WriterSerializer
from django.views.decorators.http import require_POST

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
    query = request.GET.get('search', '')

    if query:
        writers = User.objects.filter(is_writer=True, username__icontains=query)
    else:
        writers = User.objects.filter(is_writer=True)

    writers_ser = WriterSerializer(writers, many=True, context={'request': request}).data
    
    context = {
        'writers': writers_ser,
        'search_query': query,
    }
    
    return render(request, 'portal/blog/client/client-writer-list.html', context)
