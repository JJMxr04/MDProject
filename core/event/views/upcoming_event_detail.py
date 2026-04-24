import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotFound
from django.shortcuts import get_object_or_404, render

from core.event.models import Event
from core.event.serializers.event import EventWithMarketsSerializer

logger = logging.getLogger(__name__)


@login_required(login_url='/auth/login/')
def upcoming_event_detail(request, event_id):
    if event_id is None:
        logger.error("Received None as event_id.")
        return HttpResponseNotFound("Invalid event ID")

    try:
        event = get_object_or_404(
            Event.objects.select_related("home_team", "away_team", "sport"),
            pk=event_id,
        )
    except ValueError:
        return HttpResponseNotFound("Invalid event ID")

    try:
        serialized = EventWithMarketsSerializer(event).data
        markets = serialized.get("markets", []) or []
    except Exception:
        logger.exception("Error serializing markets for event %s", event_id)
        markets = []

    return render(request, 'portal/event/upcoming_event_detail.html', {
        'event': event,
        'markets': markets,
    })
