from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.blog.writer.decorator import writer_required
from core.event.models import Event, Sport  # Adjust import according to your project's structure
from django.utils.dateparse import parse_date
from core.event.serializers.event import EventSerializer
import json
from uuid import UUID
from django.core.serializers.json import DjangoJSONEncoder

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from core.match.models import Match
from core.match.serializers.match import MatchSerializer
from core.event.models import Event
from core.event.serializers.event import EventSerializer, EventBookmakerSerializer
from core.game.models import Game
from django.contrib.auth.decorators import login_required
import json

from django.http import JsonResponse
from django.views.decorators.http import require_GET,require_POST
from django.shortcuts import get_object_or_404
from django.utils import timezone

from datetime import datetime, timedelta

@require_GET
@login_required(login_url='/auth/login/')
@writer_required
def writer_events(request):
    # Get the current date and time
    now = timezone.now()
    # Calculate the date one week from now
    one_week_later = now + timedelta(weeks=1)
    
    # Fetch unique events from today up to a week from now that have bookmakers
    events = Event.objects.filter(commence_time__range=(now, one_week_later), bookmakers__isnull=False).distinct()
    event_ser = EventSerializer(events, many=True).data
    return JsonResponse({
        'events': event_ser
    })


@require_GET
@login_required(login_url='/auth/login/')
@writer_required
def writer_event_BMO(request, event_id):

    event = get_object_or_404(Event, id=event_id)
    event_bookmaker_serializer = EventBookmakerSerializer(event).data

    # Return the serialized data as a JSON response
    return JsonResponse({
        'event_bookmakers': event_bookmaker_serializer
    })

