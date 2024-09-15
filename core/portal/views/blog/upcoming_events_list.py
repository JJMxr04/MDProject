from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.event.models import Event, Sport  # Adjust import according to your project's structure
from django.utils.dateparse import parse_date
from core.event.serializers.event import EventSerializer
import json
from uuid import UUID
from django.core.serializers.json import DjangoJSONEncoder


class UUIDEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        return super().default(obj)

@login_required(login_url='/auth/login/')
def upcoming_events_list(request):
    # Fetch query parameters for filtering
    search_query = request.GET.get('search', '')
    selected_sport = request.GET.get('sport', '')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # Prepare filters
    filters = {}
    if search_query:
        filters['title__icontains'] = search_query
    if selected_sport:
        filters['sport__key'] = selected_sport
    if start_date:
        filters['commence_time__gte'] = parse_date(start_date)
    if end_date:
        filters['commence_time__lte'] = parse_date(end_date)

    # Fetch events with filtering
    events = EventSerializer(Event.objects.filter(**filters).order_by('commence_time'),many=True).data
    
    # Serialize events
    
    # Convert to JSON using custom encoder


    context = {
        'events': events,
        'sports': list(Sport.objects.all()),
        'search_query': search_query,
        'selected_sport': selected_sport,
        'start_date': start_date,
        'end_date': end_date
    }

    return render(request, 'portal/blog/upcoming-events-list.html', context)
