from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from core.match.models import Match
from core.match.serializers.match import MatchSerializer
from core.event.models import Event
from core.event.serializers.event import EventSerializer, EventWithMarketsSerializer
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
def event_outcomes(request, event_id):

    event = get_object_or_404(Event, id=event_id)
    return JsonResponse({
        'event': EventWithMarketsSerializer(event).data,
    })

