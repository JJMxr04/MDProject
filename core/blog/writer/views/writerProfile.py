from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.blog.writer.decorator import writer_required
from core.event.models import Event, Sport  # Adjust import according to your project's structure
from django.utils.dateparse import parse_date
from core.event.serializers.event import EventSerializer
import json
from uuid import UUID
from django.core.serializers.json import DjangoJSONEncoder
from core.blog.writer.forms import WriterProfileForm
from django.contrib.auth import get_user_model

User = get_user_model()


@login_required(login_url='/auth/login/')
@writer_required
def writer_profile(request):  # Ensure article_id is included
    
    form = WriterProfileForm(instance=request.user)
    if request.method =='POST':
        form = WriterProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('core-portal:profiles')
   
    context = {'WriterProfileForm':form}
    print(context)
    return render(request,'portal/blog/writer/writer-profile.html', context)