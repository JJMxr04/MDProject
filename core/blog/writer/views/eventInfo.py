from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db import models  # Import models here
from core.blog.writer.decorator import writer_required
from core.event.models import Event  # Adjust import according to your project's structure
from datetime import timedelta
from django.utils import timezone
from core.event.serializers.event import EventSerializer

@require_GET
@login_required(login_url='/auth/login/')
@writer_required
def writer_events(request):
    # Get the current date and time
    now = timezone.now()
    # Calculate the date one week from now
    one_week_later = now + timedelta(weeks=1)

    # Get the search term from query parameters
    search_term = request.GET.get('search', '').strip()

    # Fetch unique events from today up to a week from now that have bookmakers
    events = Event.objects.filter(commence_time__range=(now, one_week_later), bookmakers__isnull=False).distinct()

    # If there's a search term, filter the events
    if search_term:
        # Filter by event title, sport title, home team, or away team
        events = events.filter(
            models.Q(title__icontains=search_term) |  # Event title
            models.Q(sport_title__icontains=search_term) |  # Sport title
            models.Q(home_team__icontains=search_term) |  # Home team
            models.Q(away_team__icontains=search_term)  # Away team
        )

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

