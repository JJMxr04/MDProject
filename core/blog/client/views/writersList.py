from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.blog.writer.models import Article
from core.blog.client.models import Subscription  # Adjust import according to your project's structure
from core.user.models import User
from core.user.serializers import WriterSerializer

@login_required(login_url='/auth/login/')
def writer_list(request):

    writers = User.objects.filter(is_writer=True)
    writers_ser = WriterSerializer(writers, many=True).data 
    # Get all active subscriptions of the current user
    context={'writers':writers_ser}
    print(writers_ser)
    
    return render(request, 'portal/blog/client/client-writer-list.html',context)
