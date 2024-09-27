from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.event.models import Event, Sport  # Adjust import according to your project's structure
from django.utils.dateparse import parse_date
from core.event.serializers.event import EventSerializer
import json
from uuid import UUID
from django.core.serializers.json import DjangoJSONEncoder


@login_required(login_url='/auth/login/')
def client_dashboard(request):

    return render(request,'portal/blog/client/client-dashboard.html')