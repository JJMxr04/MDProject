from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from core.event.models import Event 
from core.event.serializers.event import EventSerializer, EventBookmakerSerializer
import json



@login_required(login_url='/auth/login/')
def upcoming_event_detail(request, event_id):
    print('event1')
    # Attempt to retrieve the event or log an error if not found
    try:
        print('event2')
        event = get_object_or_404(Event, pk=event_id)
    except Event.DoesNotExist:
        print('event3')
        logger.error(f"Event with ID {event_id} does not exist.")
        return HttpResponseNotFound("Event not found")
    print('event4')
    # Serialize the event data for the template
    try:
        print('event5')
        event_data = EventBookmakerSerializer(event).data
    except Exception as e:
        print('event6')
        logger.error(f"Error serializing event data: {str(e)}")
        return HttpResponseNotFound("Error processing event data")
    print('event7')
    # Add the event data to the context for rendering
    # context = {
    #     'event': event_data,
    # }
        context = {
        'event': '{}',
    }

    return redirect('core-portal:portal-dashboard')

    # return render(request, 'portal/event/upcoming_event_detail.html', context)