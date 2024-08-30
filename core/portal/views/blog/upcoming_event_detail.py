from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from core.event.models import Event  # Adjust import according to your project's structure


@login_required(login_url='/auth/login/')
def upcoming_event_detail(request, event_id):
    event = get_object_or_404(Event, pk=event_id)

    # Add necessary processing logic for bookmakers, markets, and outcomes
    # Assuming event.bookmakers is a preprocessed list of dictionaries with relevant data

    context = {
        'event': event,
    }

    return render(request, 'portal/blog/event_detail.html', context)
