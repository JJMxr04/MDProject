from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.user.models import User
from core.user.serializers import WriterSerializer

@login_required(login_url='/auth/login/')
def writer_list(request):
    # Get the search query from the request's GET parameters
    query = request.GET.get('search', '')

    # Filter writers by username if a search query is present
    if query:
        writers = User.objects.filter(is_writer=True, username__icontains=query)
    else:
        writers = User.objects.filter(is_writer=True)
    
    writers_ser = WriterSerializer(writers, many=True).data 
    
    context = {
        'writers': writers_ser,
        'search_query': query,  # Pass the search query back to the template
    }
    
    return render(request, 'portal/blog/client/client-writer-list.html', context)
